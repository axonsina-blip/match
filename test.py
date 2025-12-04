from fastapi import FastAPI, Response, Query
import requests
import uvicorn
from urllib.parse import urljoin, quote

app = FastAPI()

def rewrite_m3u8(content, base_url, referer, origin):
    lines = content.decode().split("\n")
    rewritten = []

    for line in lines:
        if line.endswith(".ts") or line.endswith(".m3u8"):
            real_url = urljoin(base_url, line)
            proxy_url = (
                f"http://localhost:8000/stream?"
                f"url={quote(real_url)}&referer={quote(referer)}&origin={quote(origin)}"
            )
            rewritten.append(proxy_url)
        else:
            rewritten.append(line)
    return "\n".join(rewritten).encode()

@app.get("/stream")
def stream(url: str = Query(...), referer: str = Query(""), origin: str = Query("")):
    headers = {"User-Agent": "Mozilla/5.0"}
    if referer: headers["Referer"] = referer
    if origin: headers["Origin"] = origin

    r = requests.get(url, headers=headers, verify=False)
    content_type = r.headers.get("Content-Type", "")

    if "application/vnd.apple.mpegurl" in content_type or ".m3u8" in url:
        rewritten = rewrite_m3u8(r.content, url, referer, origin)
        return Response(
            content=rewritten,
            media_type="application/vnd.apple.mpegurl",
            headers={"Access-Control-Allow-Origin": "*"}  # ✅ Add CORS header
        )

    return Response(
        content=r.content,
        media_type=content_type,
        headers={"Access-Control-Allow-Origin": "*"}  # ✅ Add CORS header
    )

if __name__ == "__main__":
    print("🔥 Proxy Server running on http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
