"""
Backend module - FastAPI server + Playwright browser control
Handles communication with DeepSeek/Gemini web chat
"""

import asyncio
import sys
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

app = FastAPI()

# Global state
page = None
browser = None
context = None
playwright_instance = None
current_ai = "deepseek"


class ChatRequest(BaseModel):
    prompt: str
    target_ai: str = "deepseek"


class InitRequest(BaseModel):
    target_ai: str = "deepseek"


@app.get("/health")
async def health_check():
    return {"status": "ok", "browser": page is not None, "ai": current_ai}


@app.get("/browser_status")
async def browser_status():
    return {"initialized": page is not None, "ai": current_ai}


def get_browser_executable():
    """Find Chrome/Edge executable on system"""
    import platform
    system = platform.system()
    
    if system == "Windows":
        paths = [
            os.path.expandvars(r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%PROGRAMFILES%\Microsoft\Edge\Application\msedge.exe"),
            os.path.expandvars(r"%PROGRAMFILES(X86)%\Microsoft\Edge\Application\msedge.exe"),
        ]
    elif system == "Darwin":
        paths = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        ]
    else:
        paths = [
            "/usr/bin/google-chrome",
            "/usr/bin/chromium-browser",
            "/usr/bin/microsoft-edge",
        ]
    
    for p in paths:
        if os.path.exists(p):
            return p
    return None


@app.post("/init_browser")
async def init_browser(req: InitRequest):
    global page, browser, context, playwright_instance, current_ai
    
    try:
        from playwright.async_api import async_playwright
        
        target_ai = req.target_ai.lower()
        current_ai = target_ai
        
        # Profile directory for persistent login
        profile_dir = os.path.join(os.path.expanduser("~"), ".hm_translator", "Profiles")
        os.makedirs(profile_dir, exist_ok=True)
        
        exec_path = get_browser_executable()
        
        playwright_instance = await async_playwright().start()
        
        launch_args = [
            "--start-maximized",
            "--disable-blink-features=AutomationControlled",
        ]
        
        # Launch persistent context (keeps login session)
        context = await playwright_instance.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            executable_path=exec_path,
            headless=False,
            args=launch_args,
            permissions=["clipboard-read", "clipboard-write"],
            no_viewport=True,
        )
        
        page = context.pages[0] if context.pages else await context.new_page()
        
        # Navigate to AI chat
        if target_ai == "gemini":
            url = "https://gemini.google.com/"
        else:
            url = "https://chat.deepseek.com/"
        
        await page.goto(url, wait_until="domcontentloaded")
        await asyncio.sleep(3)
        
        return {"status": "ok", "message": f"Browser initialized for {target_ai}"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/stop_generation")
async def stop_generation():
    """Stop AI generation if running"""
    global page
    if not page:
        raise HTTPException(status_code=400, detail="Browser not initialized")
    
    try:
        # Try clicking stop button
        stop_btn = page.locator("button[aria-label*='Stop'], button[aria-label*='Dừng'], .ds-icon-button")
        if await stop_btn.count() > 0:
            await stop_btn.first.click()
        return {"status": "stopped"}
    except:
        return {"status": "no_generation"}


@app.post("/chat")
async def chat_with_ai(req: ChatRequest):
    """Send message to AI and wait for response"""
    global page, current_ai
    
    if not page:
        raise HTTPException(status_code=400, detail="Browser not initialized")
    
    try:
        # Determine keyboard modifier
        cmd_ctrl = "Meta" if sys.platform == "darwin" else "Control"
        
        # JavaScript to copy text to clipboard
        js_copy_code = """
        async (text) => {
            try {
                await navigator.clipboard.writeText(text);
            } catch (e) {
                const textArea = document.createElement("textarea");
                textArea.value = text;
                document.body.appendChild(textArea);
                textArea.focus();
                textArea.select();
                document.execCommand("copy");
                document.body.removeChild(textArea);
            }
        }
        """
        
        # Copy prompt to clipboard
        await page.evaluate(js_copy_code, req.prompt)
        await asyncio.sleep(0.2)
        
        if current_ai == "gemini":
            # Gemini: use .ql-editor
            input_box = page.locator(".ql-editor").first
            await input_box.wait_for(state="visible", timeout=30000)
            await input_box.click()
            
            # Clear existing text
            await page.keyboard.press(f"{cmd_ctrl}+A")
            await page.keyboard.press("Backspace")
            await asyncio.sleep(0.2)
            
            # Paste
            await page.keyboard.press(f"{cmd_ctrl}+V")
            await asyncio.sleep(0.5)
            await page.keyboard.press("Space")
            await asyncio.sleep(0.5)
            
            # Send
            send_btn = page.locator("button[aria-label*='Send'], button[aria-label*='Gửi']").first
            if await send_btn.count() > 0 and await send_btn.is_visible():
                await send_btn.click()
            else:
                await page.keyboard.press("Enter")
        else:
            # DeepSeek: use textarea
            textarea = page.locator("textarea").first
            await textarea.wait_for(state="visible", timeout=30000)
            await textarea.click()
            
            # Clear existing text
            await page.keyboard.press(f"{cmd_ctrl}+A")
            await page.keyboard.press("Backspace")
            await asyncio.sleep(0.2)
            
            # Paste
            await page.keyboard.press(f"{cmd_ctrl}+V")
            await asyncio.sleep(0.5)
            
            # Press Enter or click send button  
            await asyncio.sleep(0.3)
            send_btn = page.locator("div[class*='chat-input'] button, button[aria-label*='Send']").first
            if await send_btn.count() > 0 and await send_btn.is_visible():
                await send_btn.click()
            else:
                await page.keyboard.press("Enter")
        
        # Wait for response
        await asyncio.sleep(3)
        
        # Wait for AI to finish generating (max 15 minutes for large batches)
        start_time = asyncio.get_event_loop().time()
        last_length = 0
        idle_seconds = 0
        max_wait = 900  # 15 minutes max
        
        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > max_wait:
                return {"status": "timeout", "text": "Timeout"}
            
            # Check if generation is complete by monitoring text length
            if current_ai == "gemini":
                messages = page.locator("model-response, message-content, .message-content, .markdown")
            else:
                messages = page.locator(".ds-message")
            
            msg_count = await messages.count()
            if msg_count == 0:
                await asyncio.sleep(1)
                continue
            
            # Get last message
            last_msg = messages.last
            
            # Get text content
            if current_ai == "deepseek":
                md_blocks = last_msg.locator(".ds-markdown")
                if await md_blocks.count() > 0:
                    text_for_len = await md_blocks.last.inner_text()
                else:
                    text_for_len = await last_msg.inner_text()
            else:
                text_for_len = await last_msg.inner_text()
            
            current_length = len(text_for_len)
            
            if current_length == last_length and current_length > 0:
                idle_seconds += 1
                if idle_seconds >= 6:
                    # AI finished generating
                    break
            else:
                idle_seconds = 0
                last_length = current_length
            
            await asyncio.sleep(1)
        
        # Extract final text - prefer code block content
        if current_ai == "deepseek":
            md_blocks = last_msg.locator(".ds-markdown")
            if await md_blocks.count() > 0:
                # Check for code blocks (pre elements)
                pre_elements = md_blocks.last.locator("pre")
                if await pre_elements.count() > 0:
                    final_text = await pre_elements.last.inner_text()
                else:
                    final_text = await md_blocks.last.inner_text()
            else:
                final_text = await last_msg.inner_text()
        else:
            pre_elements = last_msg.locator("pre")
            if await pre_elements.count() > 0:
                final_text = await pre_elements.last.inner_text()
            else:
                final_text = await last_msg.inner_text()
        
        # Scroll to end
        await page.keyboard.press("End")
        
        return {"status": "ok", "text": final_text}
    
    except Exception as e:
        return {"status": "error", "text": str(e)}


def start_server(port: int):
    """Start the FastAPI server"""
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    start_server(args.port)
