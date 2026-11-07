// Only the external provider boundary is synthetic. Application routes, parsing,
// SHA binding, authorisation, persistence and finalization execute unchanged.
const nativeFetch = globalThis.fetch;
globalThis.fetch = async (input, options) => {
  const url = new URL(typeof input === 'string' || input instanceof URL ? input : input.url);
  if (url.origin === 'https://api.github.com') {
    if (url.pathname === '/repos/acceptance/local-project')
      return Response.json({default_branch: 'main'});
    if (url.pathname === '/repos/acceptance/local-project/commits/main')
      return Response.json({sha: 'a'.repeat(40), commit: {message: 'Synthetic acceptance fixture', author: {name: 'Acceptance fixture', date: '2026-10-17T00:00:00Z'}}});
    return Response.json({message: 'Fixture repository not found'}, {status: 404});
  }
  if (!['127.0.0.1', 'localhost'].includes(url.hostname)) throw new Error('External provider excluded from this acceptance scope');
  return nativeFetch(input, options);
};
