"""QZoneCapsule 命令行入口。"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .auth import load_session, login_with_cookie, login_with_qrcode, save_session
from .client import QzoneError
from .exporter import export_bundle
from .store import Store
from .sync import SyncOptions, run_sync

app = typer.Typer(
    name="qzone",
    help="把 QQ 空间的说说、相册原图与时间线归档到本地。",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


@app.command()
def login(
    cookie: str | None = typer.Option(None, "--cookie", "-c", help="直接粘贴浏览器里的 Cookie"),
    qrcode: bool = typer.Option(False, "--qrcode", "-q", help="使用手机 QQ 扫码登录"),
) -> None:
    """登录并保存会话凭证。"""
    try:
        if qrcode:
            console.print("二维码已保存为 [bold]qrcode.png[/bold]，请用手机 QQ 扫描。")
            result = login_with_qrcode()
        else:
            if not cookie:
                cookie = typer.prompt("粘贴 Cookie（含 p_skey、p_uin）", hide_input=True)
            result = login_with_cookie(cookie)
    except QzoneError as exc:
        console.print(f"[red]登录失败：{exc}[/red]")
        raise typer.Exit(1) from exc

    path = save_session(result["cookie"], result.get("nickname", ""))
    console.print(f"[green]登录成功[/green] QQ {result['uin']}，会话已保存到 {path}（权限 600）")


@app.command()
def sync(
    out: Path = typer.Option(Path("backup"), "--out", "-o", help="备份目录"),
    albums: bool = typer.Option(True, "--albums/--no-albums", help="是否同步相册"),
    moods: bool = typer.Option(True, "--moods/--no-moods", help="是否同步说说"),
    media: bool = typer.Option(True, "--media/--no-media", help="是否下载图片/视频"),
    limit: int = typer.Option(0, "--limit", help="最多同步多少个相册，0 为不限"),
    interval: float = typer.Option(0.8, "--interval", help="请求间隔秒数，防止触发风控"),
) -> None:
    """同步相册与说说到本地 SQLite 和媒体目录。"""
    session = _require_session()
    report = run_sync(
        session,
        SyncOptions(out, albums, moods, media, limit=limit, interval=interval),
        lambda message, _: console.print(message, markup=False),
    )
    console.print(f"相册 {report.albums} · 照片 {report.photos} · 说说 {report.moods} · 失败 {report.failed}")
    console.print(f"离线查看器：{report.index}")
    if report.state != "complete":
        raise typer.Exit(1)


@app.command()
def export(
    out: Path = typer.Option(Path("backup"), "--out", "-o", help="备份目录"),
) -> None:
    """从已有存档重新生成离线 HTML。"""
    session = load_session()
    uin = (session or {}).get("uin", "")
    if not uin:
        console.print("[red]未找到会话，请先运行 qzone login[/red]")
        raise typer.Exit(1)

    out = out.expanduser().resolve()
    with Store(out / "qzone.db") as store:
        index = export_bundle(store, uin, out, (session or {}).get("nickname", ""))
    console.print(f"已生成 [bold]{index}[/bold]")


@app.command()
def status(
    out: Path = typer.Option(Path("backup"), "--out", "-o", help="备份目录"),
) -> None:
    """查看当前存档的统计信息。"""
    session = load_session()
    uin = (session or {}).get("uin", "")
    db_path = out.expanduser().resolve() / "qzone.db"
    if not uin or not db_path.exists():
        console.print("[red]没有找到存档[/red]")
        raise typer.Exit(1)

    with Store(db_path) as store:
        stats = store.stats(uin)

    table = Table(show_header=False)
    table.add_row("QQ", uin)
    table.add_row("相册", str(stats["albums"]))
    table.add_row("照片", str(stats["photos"]))
    table.add_row("已下载", str(stats["downloaded"]))
    table.add_row("说说", str(stats["moods"]))
    table.add_row("说说图片", str(stats["mood_media"]))
    console.print(table)


@app.command()
def verify(
    out: Path = typer.Option(Path("backup"), "--out", "-o", help="备份目录"),
) -> None:
    """检查文件完整性、EXIF 写入情况与缺失时间。"""
    session = load_session()
    uin = (session or {}).get("uin", "")
    out = out.expanduser().resolve()
    db_path = out / "qzone.db"
    if not uin or not db_path.exists():
        console.print("[red]没有找到存档[/red]")
        raise typer.Exit(1)

    missing_files = 0
    missing_time = 0
    exif_counts: dict[str, int] = {}

    with Store(db_path) as store:
        for row in store.iter_photos(uin):
            if row["local_path"] and not (out / row["local_path"]).exists():
                missing_files += 1
            if not (row["shoot_at"] or row["upload_at"]):
                missing_time += 1
            status = row["exif_status"] or "pending"
            exif_counts[status] = exif_counts.get(status, 0) + 1

    console.print(f"缺失文件：{missing_files}")
    console.print(f"缺少时间：{missing_time}")
    console.print("EXIF 状态：" + "，".join(f"{k} {v}" for k, v in sorted(exif_counts.items())))


# ---------- 内部实现 ----------


def _require_session() -> dict:
    session = load_session()
    if not session or not session.get("cookie"):
        console.print("[red]未登录，请先运行 [bold]qzone login[/bold][/red]")
        raise typer.Exit(1)
    return session


if __name__ == "__main__":
    app()
