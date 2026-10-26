export default {
  fetch(request: Request): Response {
    const path = new URL(request.url).pathname;
    if (path !== '/api/health') {
      return Response.json({ error: 'Not found' }, { status: 404 });
    }
    if (request.method !== 'GET') {
      return Response.json(
        { error: 'Method not allowed' },
        { status: 405, headers: { Allow: 'GET' } },
      );
    }
    return Response.json({ status: 'ok', service: 'draftory-api' });
  },
} satisfies ExportedHandler<Env>;
