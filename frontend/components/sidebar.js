(function () {
  const links = document.querySelectorAll('#sidebar-nav .sidebar-link');
  const path  = window.location.pathname;

  links.forEach(link => {
    const href = link.getAttribute('href') || '';
    // Strip trailing slash for comparison
    const normalizedPath = path.replace(/\/$/, '');
    const normalizedHref = href.replace(/\/$/, '');

    if (normalizedPath === normalizedHref || normalizedPath.startsWith(normalizedHref + '/')) {
      link.classList.remove('text-slate-600', 'dark:text-slate-400');
      link.classList.add('text-red-700', 'dark:text-red-500', 'active-nav-border', 'bg-yellow-400/10');
    }
  });
})();
