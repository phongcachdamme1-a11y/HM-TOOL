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
_gemini_response_count_before = 0


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
            url = "https://gemini.google.com/app"
        else:
            url = "https://chat.deepseek.com/"
        
        await page.goto(url, wait_until="domcontentloaded")
        await asyncio.sleep(5)
        
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
        stop_btn = page.locator("button[aria-label*='Stop'], button[aria-label*='Dừng'], .ds-icon-button")
        if await stop_btn.count() > 0:
            await stop_btn.first.click()
        return {"status": "stopped"}
    except:
        return {"status": "no_generation"}


# ============================================================
# GEMINI FUNCTIONS
# ============================================================

async def _send_to_gemini(prompt_text):
    """Send prompt to Gemini using JavaScript injection + clipboard fallback"""
    global page, _gemini_response_count_before
    
    cmd_ctrl = "Meta" if sys.platform == "darwin" else "Control"
    
    # Count existing responses BEFORE sending (to detect new one later)
    js_count = """
    () => {
        let count = 0;
        let selectors = ['model-response', 'message-content', '.message-content', '[data-message-author-role="model"]'];
        for (let s of selectors) {
            let els = document.querySelectorAll(s);
            if (els.length > count) count = els.length;
        }
        return count;
    }
    """
    try:
        _gemini_response_count_before = await page.evaluate(js_count)
    except:
        _gemini_response_count_before = 0
    
    # Method 1: Try to inject text via JavaScript into contenteditable
    js_inject = """
    (text) => {
        // Try .ql-editor (Quill editor - logged in Gemini)
        let editor = document.querySelector('.ql-editor');
        if (editor) {
            editor.innerHTML = '<p>' + text.replace(/\\n/g, '</p><p>') + '</p>';
            editor.dispatchEvent(new Event('input', { bubbles: true }));
            return 'ql-editor';
        }
        // Try contenteditable div
        let editable = document.querySelector('div[contenteditable="true"]');
        if (editable) {
            editable.innerText = text;
            editable.dispatchEvent(new Event('input', { bubbles: true }));
            return 'contenteditable';
        }
        // Try textarea
        let ta = document.querySelector('textarea');
        if (ta) {
            ta.value = text;
            ta.dispatchEvent(new Event('input', { bubbles: true }));
            return 'textarea';
        }
        return null;
    }
    """
    
    inject_result = await page.evaluate(js_inject, prompt_text)
    
    if not inject_result:
        # Fallback: clipboard paste
        js_copy = """
        async (text) => {
            try { await navigator.clipboard.writeText(text); }
            catch (e) {
                const ta = document.createElement("textarea");
                ta.value = text; ta.style.position = "fixed"; ta.style.left = "-9999px";
                document.body.appendChild(ta); ta.focus(); ta.select();
                document.execCommand("copy"); document.body.removeChild(ta);
            }
        }
        """
        await page.evaluate(js_copy, prompt_text)
        await asyncio.sleep(0.3)
        
        # Find and click input
        input_box = page.locator(".ql-editor, div[contenteditable='true'], textarea").first
        await input_box.click()
        await asyncio.sleep(0.2)
        await page.keyboard.press(f"{cmd_ctrl}+A")
        await page.keyboard.press("Backspace")
        await asyncio.sleep(0.2)
        await page.keyboard.press(f"{cmd_ctrl}+V")
    
    await asyncio.sleep(1.0)
    
    # Click send button
    send_selectors = [
        "button.send-button",
        "button[aria-label='Send message']",
        "button[aria-label*='Send']",
        "button[aria-label*='Gửi']",
        "button[data-testid*='send']",
        ".send-button-container button",
        "button[mat-icon-button]",
    ]
    
    sent = False
    for selector in send_selectors:
        try:
            btn = page.locator(selector).first
            if await btn.count() > 0 and await btn.is_visible():
                await asyncio.sleep(0.3)
                await btn.click()
                sent = True
                break
        except:
            continue
    
    if not sent:
        # Fallback: Enter key
        await page.keyboard.press("Enter")
    
    return True


async def _wait_for_response_gemini():
    """Wait for Gemini response to complete with robust detection"""
    global page, _gemini_response_count_before
    
    await asyncio.sleep(5)
    
    start_time = asyncio.get_event_loop().time()
    last_text = ""
    idle_seconds = 0
    max_wait = 900  # 15 minutes max
    prev_count = getattr(sys.modules[__name__], '_gemini_response_count_before', 0)
    
    while True:
        elapsed = asyncio.get_event_loop().time() - start_time
        if elapsed > max_wait:
            return {"status": "timeout", "text": "Timeout - qua 15 phut khong co phan hoi"}
        
        # Use JavaScript to get the LATEST response (newer than prev_count)
        js_get_response = """
        (prevCount) => {
            // Try multiple response containers
            let selectors = ['model-response', 'message-content', '.message-content', '[data-message-author-role="model"]'];
            let responses = [];
            
            for (let s of selectors) {
                let els = document.querySelectorAll(s);
                if (els.length > 0) {
                    responses = els;
                    break;
                }
            }
            
            if (responses.length === 0) {
                return {text: '', found: false, count: 0};
            }
            
            // Get the LAST response (newest)
            let last = responses[responses.length - 1];
            
            // Check if this is a NEW response (count > prevCount)
            let isNew = responses.length > prevCount;
            
            // Extract text - prefer code blocks
            let codeBlock = last.querySelector('pre code, pre, code-block, .code-block');
            let text = '';
            if (codeBlock) {
                text = codeBlock.innerText || codeBlock.textContent || '';
            } else {
                text = last.innerText || last.textContent || '';
            }
            
            return {text: text, found: true, count: responses.length, isNew: isNew};
        }
        """
        
        try:
            result = await page.evaluate(js_get_response, prev_count)
        except:
            await asyncio.sleep(2)
            continue
        
        current_text = result.get('text', '')
        found = result.get('found', False)
        is_new = result.get('isNew', False)
        
        if not found or not current_text.strip():
            await asyncio.sleep(2)
            continue
        
        # Only process if it's a NEW response
        if not is_new and elapsed < 15:
            await asyncio.sleep(2)
            continue
        
        # Compare with previous text to detect generation complete
        if current_text == last_text and len(current_text) > 20:
            idle_seconds += 1
            if idle_seconds >= 10:
                # Response complete - text hasn't changed for 10 seconds
                break
        else:
            idle_seconds = 0
            last_text = current_text
        
        await asyncio.sleep(1)
    
    return {"status": "ok", "text": last_text}


# ============================================================
# DEEPSEEK FUNCTIONS
# ============================================================

async def _send_to_deepseek(prompt_text):
    """Send prompt to DeepSeek"""
    global page
    
    cmd_ctrl = "Meta" if sys.platform == "darwin" else "Control"
    
    # Copy to clipboard
    js_copy = """
    async (text) => {
        try { await navigator.clipboard.writeText(text); }
        catch (e) {
            const ta = document.createElement("textarea");
            ta.value = text; ta.style.position = "fixed"; ta.style.left = "-9999px";
            document.body.appendChild(ta); ta.focus(); ta.select();
            document.execCommand("copy"); document.body.removeChild(ta);
        }
    }
    """
    await page.evaluate(js_copy, prompt_text)
    await asyncio.sleep(0.3)
    
    # DeepSeek: use textarea
    textarea = page.locator("textarea").first
    await textarea.wait_for(state="visible", timeout=30000)
    await textarea.click()
    
    # Clear and paste
    await page.keyboard.press(f"{cmd_ctrl}+A")
    await page.keyboard.press("Backspace")
    await asyncio.sleep(0.2)
    await page.keyboard.press(f"{cmd_ctrl}+V")
    await asyncio.sleep(0.5)
    
    # Send
    await asyncio.sleep(0.3)
    send_btn = page.locator("div[class*='chat-input'] button, button[aria-label*='Send']").first
    if await send_btn.count() > 0 and await send_btn.is_visible():
        await send_btn.click()
    else:
        await page.keyboard.press("Enter")
    
    return True


async def _wait_for_response_deepseek():
    """Wait for DeepSeek response to complete"""
    global page
    
    await asyncio.sleep(3)
    
    start_time = asyncio.get_event_loop().time()
    last_length = 0
    idle_seconds = 0
    max_wait = 900
    
    while True:
        elapsed = asyncio.get_event_loop().time() - start_time
        if elapsed > max_wait:
            return {"status": "timeout", "text": "Timeout"}
        
        messages = page.locator(".ds-message")
        msg_count = await messages.count()
        if msg_count == 0:
            await asyncio.sleep(1)
            continue
        
        last_msg = messages.last
        md_blocks = last_msg.locator(".ds-markdown")
        if await md_blocks.count() > 0:
            text_for_len = await md_blocks.last.inner_text()
        else:
            text_for_len = await last_msg.inner_text()
        
        current_length = len(text_for_len)
        
        if current_length == last_length and current_length > 0:
            idle_seconds += 1
            if idle_seconds >= 6:
                break
        else:
            idle_seconds = 0
            last_length = current_length
        
        await asyncio.sleep(1)
    
    # Extract final text
    md_blocks = last_msg.locator(".ds-markdown")
    if await md_blocks.count() > 0:
        pre_elements = md_blocks.last.locator("pre")
        if await pre_elements.count() > 0:
            final_text = await pre_elements.last.inner_text()
        else:
            final_text = await md_blocks.last.inner_text()
    else:
        final_text = await last_msg.inner_text()
    
    return {"status": "ok", "text": final_text}


# ============================================================
# MAIN CHAT ENDPOINT
# ============================================================

@app.post("/chat")
async def chat_with_ai(req: ChatRequest):
    """Send message to AI and wait for response"""
    global page, current_ai
    
    if not page:
        raise HTTPException(status_code=400, detail="Browser not initialized")
    
    try:
        if current_ai == "gemini":
            await _send_to_gemini(req.prompt)
            result = await _wait_for_response_gemini()
        else:
            await _send_to_deepseek(req.prompt)
            result = await _wait_for_response_deepseek()
        
        # Scroll to end
        try:
            await page.keyboard.press("End")
        except:
            pass
        
        return result
    
    except Exception as e:
        return {"status": "error", "text": str(e)}


# ============================================================
# DEBUG ENDPOINT - helps identify selectors on current page
# ============================================================

@app.get("/debug_selectors")
async def debug_selectors():
    """Debug: check which selectors exist on current page"""
    global page
    if not page:
        return {"error": "No page"}
    
    js_debug = """
    () => {
        let results = {};
        let selectors = [
            '.ql-editor', 'div[contenteditable="true"]', 'textarea',
            'model-response', 'message-content', '.message-content',
            '.ds-message', '.ds-markdown',
            'button[aria-label*="Send"]', '.send-button',
            'rich-textarea', '.text-input-field'
        ];
        for (let s of selectors) {
            let els = document.querySelectorAll(s);
            results[s] = els.length;
        }
        results['url'] = window.location.href;
        results['title'] = document.title;
        return results;
    }
    """
    try:
        return await page.evaluate(js_debug)
    except Exception as e:
        return {"error": str(e)}


def start_server(port: int):
    """Start the FastAPI server"""
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    start_server(args.port)
