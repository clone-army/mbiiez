/*------------------------------------------------------------------
* Bootstrap Simple Admin Template
* Version: 3.0
* Author: Alexis Luna
* Website: https://github.com/alexis-luna/bootstrap-simple-admin-template
-------------------------------------------------------------------*/
(function() {
    'use strict';

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
})();

