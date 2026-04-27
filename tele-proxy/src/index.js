export default {
  async fetch(request) {
    const url = new URL(request.url);
    
    // We check if the request has a ?mime=m3u8 query param
    const mimeParam = url.searchParams.get("mime");

    const targetUrl = `https://api.telegram.org${url.pathname}`;

    const modifiedRequest = new Request(targetUrl, {
      method: request.method,
      headers: request.headers,
      body: request.body
    });

    const response = await fetch(modifiedRequest);
    
    const newHeaders = new Headers(response.headers);
    newHeaders.set("Access-Control-Allow-Origin", "*");
    newHeaders.set("Access-Control-Allow-Headers", "Range, Content-Type");
    newHeaders.set("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS");

    if (mimeParam === "m3u8") {
      newHeaders.set("Content-Type", "application/vnd.apple.mpegurl");
    } else if (mimeParam === "ts") {
      newHeaders.set("Content-Type", "video/MP2T");
    } else if (response.headers.get("Content-Type") === "application/octet-stream") {
      // If it's a small file (less than 1MB), it's likely an m3u8 playlist that telegram labeled as octet-stream
      const contentLength = response.headers.get("Content-Length");
      if (contentLength && parseInt(contentLength) < 1024 * 1024) {
         newHeaders.set("Content-Type", "application/vnd.apple.mpegurl");
      }
    }

    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: newHeaders
    });
  }
};
