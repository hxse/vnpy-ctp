"""GitHub Release 的有限请求；令牌只通过请求头传递。"""

import json
import os
import re
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen


class Github:
    def __init__(self, repository: str):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*", repository):
            raise ValueError("仓库必须为 owner/name")
        self.repository = repository
        self.token = os.environ["GH_TOKEN"]

    def request(self, method: str, path: str, *, payload=None, content=None):
        upload = content is not None
        origin = "https://uploads.github.com" if upload else "https://api.github.com"
        headers = {
            "Authorization": "Bearer " + self.token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "vnpy-ctp-wheel-release",
        }
        data = content
        if payload is not None:
            data = json.dumps(payload).encode()
            headers["Content-Type"] = "application/json"
        elif upload:
            headers["Content-Type"] = "application/octet-stream"
        request = Request(origin + f"/repos/{self.repository}/" + path, data=data,
                          headers=headers, method=method)
        try:
            with urlopen(request, timeout=180 if upload else 30) as response:
                body = response.read()
                return json.loads(body) if body else None
        except HTTPError as error:
            if error.code == 404 and method == "GET" and path.startswith("releases/tags/"):
                return None
            raise RuntimeError(f"GitHub {method} {path.split('?')[0]} 返回 HTTP {error.code}") from None

    def release(self, tag: str):
        return self.request("GET", "releases/tags/" + quote(tag, safe=""))

    def assets(self, release_id: int):
        return self.request("GET", f"releases/{release_id}/assets?per_page=100")

    def manifest(self, tag: str) -> bytes:
        url = f"https://github.com/{self.repository}/releases/download/{quote(tag, safe='')}/manifest.json"
        # 正式仓库公开；下载链接不携带令牌，也不把令牌转发到 CDN。
        with urlopen(Request(url, headers={"User-Agent": "vnpy-ctp-wheel-release"}), timeout=30) as response:
            return response.read()

    def create(self, tag: str, commit: str):
        return self.request("POST", "releases", payload={
            "tag_name": tag, "target_commitish": commit, "name": tag,
            "body": "当前提交的跨平台交易 API wheel。兼容平台、固定下载链接和 SHA256 见 manifest.json。",
            "draft": True, "prerelease": False,
        })

    def delete_asset(self, asset_id: int):
        return self.request("DELETE", f"releases/assets/{asset_id}")

    def upload(self, release_id: int, path):
        return self.request("POST", f"releases/{release_id}/assets?name={quote(path.name, safe='')}",
                            content=path.read_bytes())

    def publish(self, release_id: int):
        return self.request("PATCH", f"releases/{release_id}",
                            payload={"draft": False, "make_latest": "false"})
