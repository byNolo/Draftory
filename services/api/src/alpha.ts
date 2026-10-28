import api from './index';

// The original local API and its data contract remain independently usable.
interface AlphaEnv extends Env {
  ASSETS: Fetcher;
}

export default {
  async fetch(request: Request, env: AlphaEnv): Promise<Response> {
    const path = new URL(request.url).pathname;
    if (path === '/api' || path.startsWith('/api/')) {
      const response = await api.fetch(request, env);
      const headers = new Headers(response.headers);
      headers.set('Referrer-Policy', 'strict-origin-when-cross-origin');
      headers.set('X-Robots-Tag', 'noindex, nofollow');
      return new Response(response.body, { status: response.status, headers });
    }
    // Matched assets normally bypass this script. Unknown routes keep real 404s,
    // rather than returning HTML for missing JS/WASM or misspelled API paths.
    let response = await env.ASSETS.fetch(request);
    if (response.status < 400) return response;
    if (response.status === 404) {
      const page = await env.ASSETS.fetch(new URL('/404', request.url));
      response = new Response(request.method === 'HEAD' ? null : page.body, {
        status: 404,
        headers: page.headers,
      });
    }
    // _headers matches request paths, including missing /assets/* URLs. Do not
    // let that broad immutable rule cache a failed download across redeploys.
    const headers = new Headers(response.headers);
    headers.set('Cache-Control', 'no-store');
    return new Response(response.body, { status: response.status, headers });
  },
} satisfies ExportedHandler<AlphaEnv>;
