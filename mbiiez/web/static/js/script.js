/*------------------------------------------------------------------
* Bootstrap Simple Admin Template
* Version: 3.0
* Author: Alexis Luna
* Website: https://github.com/alexis-luna/bootstrap-simple-admin-template
-------------------------------------------------------------------*/
(function() {
    'use strict';

    // Always keep sidebar open (desktop) - see master.css [15. Mobile
    // sidebar drawer] for the mobile-only override that makes it
    // closeable again below the 768px breakpoint.
    $('#sidebar').addClass('active');
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

