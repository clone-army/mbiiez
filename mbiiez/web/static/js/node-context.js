// Bind every same-origin request/navigation to the node selected when this page loaded.
(() => {
  const node = document.querySelector('meta[name="mbiiez-node"]')?.content;
  const csrf = document.querySelector('meta[name="mbiiez-csrf"]')?.content;
  const originalFetch = window.fetch;
  window.fetch = (input, options = {}) => {
    const url = new URL(input instanceof Request ? input.url : input, location.href);
    if (url.origin === location.origin) {
      const headers = new Headers(input instanceof Request ? input.headers : options.headers);
      new Headers(options.headers).forEach((value, key) => headers.set(key, value));
      if (node && !url.searchParams.has('node')) headers.set('X-MBIIEZ-Node', node);
      if (csrf) headers.set('X-MBIIEZ-CSRF', csrf);
      options = {...options, headers};
    }
    return originalFetch(input, options);
  };
  document.addEventListener('DOMContentLoaded', () => {
    for (const link of document.querySelectorAll('a[href]')) {
      if (link.getAttribute('href').startsWith('#')) continue;
      const url = new URL(link.href, location.href);
      if (url.origin === location.origin && !url.pathname.startsWith('/assets/') && !url.searchParams.has('node')) {
        url.searchParams.set('node', node); link.href = url.href;
      }
    }
    for (const form of document.querySelectorAll('form')) {
      if (new URL(form.action, location.href).origin !== location.origin) continue;
      for (const [name, value] of [['node', node], ['csrf_token', csrf]]) {
        const input = document.createElement('input'); input.type = 'hidden'; input.name = name; input.value = value; form.append(input);
      }
    }
  });
})();

// Only retry a rejected occupied-server command after explicit user confirmation.
window.mbiiInstanceCommand = async (endpoint, instance, command) => {
  const send = force => fetch(endpoint, {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({command, force})
  });
  const response = await send(false);
  if (!response.ok && (command === 'restart' || command === 'stop')) {
    const data = await response.clone().json();
    if (String(data.error || '').includes('Players are online; explicit force is required')) {
      if (!window.confirm(`People are playing on ${instance}. ${command === 'restart' ? 'Restart' : 'Stop'} this server anyway? Players will be disconnected.`)) {
        return null;
      }
      return send(true);
    }
  }
  return response;
};
