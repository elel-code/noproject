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


def _get_start_index() -> int:
    """根据配置中的 next 计算起始下标，并做边界修正。"""
    total = len(chapter_name)
    start_index = _config.get("next", 0) or 0
    if not isinstance(start_index, int) or start_index < 0:
        start_index = 0
    if start_index > total:
        start_index = total
    return start_index


# 当前会话的“下一个待播放章节下标”，用于在 Ctrl+C 等异常退出时落盘
CURRENT_NEXT = _get_start_index()


async def main() -> int:
    """主逻辑，返回本次运行结束后的 next 下标。"""
    global CURRENT_NEXT
    # 用户名和密码从 JSON 配置读取，缺失时回退为交互输入
    username = USERNAME or input("请输入 Educoder 登录手机号/邮箱/账号: ")
    password = PASSWORD or getpass.getpass("请输入 Educoder 登录密码: ")

    total = len(chapter_name)
    # 从 CURRENT_NEXT 作为起始下标（已在加载时经过一次边界修正）
    start_index = CURRENT_NEXT
    next_index = start_index

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True, channel="chrome"
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
            await page.get_by_text("算法设计与分析2025秋季班级").click()
        page1 = await page1_info.value
        await page1.get_by_role("link", name="第一章 算法概述").click()
        async with page1.expect_popup() as page2_info:
            await page1.locator("a").filter(has_text="1.1 算法课程介绍").click()
        page2 = await page2_info.value

        play_button = page2.locator("#play")
        chapter = page2.locator("span")

        for idx, chap in enumerate(chapter_name[start_index:], start=start_index):
            label = f"[{idx + 1}/{total}] {chap}"

            await chapter.filter(has_text=chap).first.click()
            await asyncio.sleep(2)  # 等待视频加载完毕
            init_result = await page2.evaluate(
                """
() => {
    const video = document.querySelector('video');
    if (!video) {
        window.__videoDone = null;
        return 'no-video';
    }
    window.__videoDone = false;

    const handler = () => {
        window.__videoDone = true;
        video.removeEventListener('ended', handler);
    };
    video.addEventListener('ended', handler);

    video.muted = true;

    return 'ok:' + video.duration;
}
"""
            )

            # 根据初始化结果优化输出
            if isinstance(init_result, str) and init_result.startswith("ok:"):
                duration_str = init_result.split(":", 1)[1]
                try:
                    duration = float(duration_str)
                    print(f"{label} 初始化成功，视频时长约 {duration:.1f} 秒，开始播放…")
                except ValueError:
                    print(f"{label} 初始化成功，开始播放…")
            elif init_result == "no-video":
                print(f"{label} 未找到视频元素，跳过该章节。")
                continue
            else:
                print(f"{label} 初始化结果异常（{init_result}），尝试继续播放…")

            # 点击播放按钮
            await play_button.click()

            # 等待视频播完（__videoDone === true）
            await page2.wait_for_function("window.__videoDone === true", timeout=0)
            print(f"{label} 播放完成。")

            # 更新下一个待播放下标
            next_index = idx + 1
            CURRENT_NEXT = next_index

    return next_index


if __name__ == "__main__":
    # 运行主逻辑；无论正常结束还是 Ctrl+C 中断，都根据 CURRENT_NEXT 更新 next 字段
    try:
        new_next = asyncio.run(main())
        CURRENT_NEXT = new_next
    except KeyboardInterrupt:
        print("\n检测到 Ctrl+C，中断当前播放…")
    finally:
        _config["next"] = CURRENT_NEXT
        with CONFIG_PATH.open("w", encoding="utf-8") as f:
            json.dump(_config, f, ensure_ascii=False, indent=2)
        print(f"已保存进度，next = {CURRENT_NEXT}")
