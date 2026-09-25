/*------------------------------------------------------------------
* Bootstrap Simple Admin Template
* Version: 3.0
* Author: Alexis Luna
* Website: https://github.com/alexis-luna/bootstrap-simple-admin-template
-------------------------------------------------------------------*/
(function() {
    'use strict';

    // All 3 <script> tags load in <head> with no defer, so this file runs
    // while <head> is still being parsed - <body> (#sidebar, #body, the
    // toggle button, all of it) doesn't exist yet at that point. Every
    // $('#...') lookup below used to run directly at the top of the IIFE
    // and silently match nothing, so none of the .on(...) bindings ever
    // actually attached - not a new bug, just invisible before, since the
    // old CSS bug kept the sidebar permanently open regardless of whether
    // the JS did anything at all. $(fn) defers everything inside it until
    // the DOM is actually ready.
    $(function() {

    // Desktop "always open" comes from the unconditional #sidebar rule in
    // master.css alone now - no .active class needed on #sidebar itself.
    // (It used to be added here too, which is exactly what broke the
    // mobile drawer: #sidebar.active has higher specificity than the
    // plain #sidebar selector the mobile media query overrides, so as
    // long as that class was present the sidebar could never close,
    // regardless of what the mobile-open toggle below did.)
    $('#body').addClass('active');

    function closeMobileSidebar() {
        $('#sidebar').removeClass('mobile-open');
        $('#sidebar-backdrop').removeClass('show');
    }

    $('#mobileSidebarToggle').on('click', function() {
        $('#sidebar').toggleClass('mobile-open');
        $('#sidebar-backdrop').toggleClass('show');
    });

    $('#sidebar-backdrop').on('click', closeMobileSidebar);

    // Close the drawer after picking a real destination (a leaf link),
    // not after toggling a collapsible submenu open/closed.
    $('#sidebar a').not('[data-bs-toggle="collapse"]').on('click', function() {
        if (window.innerWidth <= 768) { closeMobileSidebar(); }
    });

    $(window).on('resize', function() {
        if (window.innerWidth > 768) { closeMobileSidebar(); }
    });

    }); // $(fn)
})();


// Toast notifications - window.mbiiToast(message, kind), kind one of
// 'success' | 'danger' | 'warning' | 'info'. Floats bottom-right above any
// sticky save bar so the result of a save is always visible, however far
// down the page you are. Success/info fade after a few seconds; errors and
// warnings stay until dismissed so they can't be missed.
window.mbiiToast = function (message, kind) {
    kind = kind || 'success';
    var container = document.getElementById('mbii-toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'mbii-toast-container';
        container.className = 'toast-container position-fixed end-0 p-3';
        container.style.bottom = '4rem';
        container.style.zIndex = '1090';
        // Only the toasts themselves take clicks - the empty container
        // must never block buttons underneath it.
        container.style.pointerEvents = 'none';
        document.body.appendChild(container);
    }

    var toast = document.createElement('div');
    toast.className = 'toast align-items-center border-0 text-bg-' + kind;
    toast.style.pointerEvents = 'auto';
    toast.setAttribute('role', kind === 'danger' ? 'alert' : 'status');
    toast.setAttribute('aria-live', kind === 'danger' ? 'assertive' : 'polite');
    toast.setAttribute('aria-atomic', 'true');

    var row = document.createElement('div');
    row.className = 'd-flex';
    var body = document.createElement('div');
    body.className = 'toast-body';
    body.textContent = message;
    var close = document.createElement('button');
    close.type = 'button';
    close.className = 'btn-close me-2 m-auto' + (kind === 'warning' ? '' : ' btn-close-white');
    close.setAttribute('data-bs-dismiss', 'toast');
    close.setAttribute('aria-label', 'Close');
    row.appendChild(body);
    row.appendChild(close);
    toast.appendChild(row);
    container.appendChild(toast);

    var sticky = kind === 'danger' || kind === 'warning';
    var t = new bootstrap.Toast(toast, { autohide: !sticky, delay: 5000 });
    toast.addEventListener('hidden.bs.toast', function () { toast.remove(); });
    t.show();
};

// Queue a toast to show on the next page load - for actions that end in a
// redirect (e.g. deleting or creating an instance), where a normal toast
// would vanish with the old page.
window.mbiiToastAfterRedirect = function (message, kind) {
    try {
        sessionStorage.setItem('mbiiPendingToast', JSON.stringify({ message: message, kind: kind || 'success' }));
    } catch (e) { /* storage blocked - the redirect still happens, just without the toast */ }
};

document.addEventListener('DOMContentLoaded', function () {
    var pending = null;
    try {
        pending = JSON.parse(sessionStorage.getItem('mbiiPendingToast') || 'null');
        sessionStorage.removeItem('mbiiPendingToast');
    } catch (e) { pending = null; }
    if (pending && pending.message) window.mbiiToast(pending.message, pending.kind);
});
