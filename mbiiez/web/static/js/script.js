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

