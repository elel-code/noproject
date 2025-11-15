import asyncio
import json
import getpass
from pathlib import Path


from playwright.async_api import async_playwright

CONFIG_PATH = Path(__file__).with_name("config.json")


def load_config(path=CONFIG_PATH):
    """从本地 JSON 配置文件读取账号和章节信息。"""
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


_config = load_config()
chapter_name = _config.get("chapters", ["1.1", "1.2"])
USERNAME = _config.get("username", "")
PASSWORD = _config.get("password", "")


async def main():
    # 用户名和密码从 JSON 配置读取，缺失时回退为交互输入
    username = USERNAME or input("请输入 Educoder 登录手机号/邮箱/账号: ")
    password = PASSWORD or getpass.getpass("请输入 Educoder 登录密码: ")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False, channel="chrome"
        )  # 使用系统浏览器
        page = await browser.new_page()
        await page.goto("https://www.educoder.net/")  # 跳转主页

        await page.get_by_text("登录 / 注册").click()
        textlocator = page.get_by_role("textbox", name="请输入有效的手机号/邮箱号/账号")
        await textlocator.click()
        await textlocator.fill(username)  # 输入用户名（软编码）
        textlocator = page.get_by_role("textbox", name="密码")
        await textlocator.click()
        await textlocator.fill(password)  # 输入密码（软编码）
        await page.get_by_role("button", name="登录").click()

        await page.get_by_role("banner").locator("img").click()
        async with page.expect_popup() as page1_info:
            await page.get_by_text(
                "算法设计与分析2025秋季班级刘锦隐藏715435414"
            ).click()
        page1 = await page1_info.value
        await page1.get_by_role("link", name="第一章 算法概述").click()
        async with page1.expect_popup() as page2_info:
            await page1.locator("a").filter(has_text="1.1 算法课程介绍").click()
        page2 = await page2_info.value

        play_button = page2.locator("#play")
        chapter = page2.locator("span")

        for chap in chapter_name:

            await chapter.filter(has_text=chap).first.click()
            await asyncio.sleep(2)  # 等待视频加载完毕
            await page2.evaluate(
                """
                () => {
                    const video = document.querySelector('video');
                    if (!video) {
                        window.__videoDone = null;  // 标记失败情况
                        return;
                    }
                    // 每次章节切换都重置
                    window.__videoDone = false;
                    // 使用 addEventListener，避免站点自身重置 onended 导致监听丢失
                    const handler = () => {
                        window.__videoDone = true;
                        console.log('>>> 视频播放结束');
                        video.removeEventListener('ended', handler);
                    };
                    video.addEventListener('ended', handler);
                }
            """
            )

            # 4. 点击播放按钮

            await play_button.click()

            # 5. 等待视频播完（__videoDone === true）
            await page2.wait_for_function("window.__videoDone === true")

        await page2.pause()


asyncio.run(main())
