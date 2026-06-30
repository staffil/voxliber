/* =========================================
   Voxliber — Sidebar JS
   ========================================= */

(function() {
  'use strict';

  const COLLAPSE_KEY = 'vox-sidebar-collapsed';
  const THEME_KEY    = 'vox-theme';

  /* ---- Sidebar collapse (desktop) ---- */
  function applyCollapse() {
    const sidebar = document.getElementById('voxSidebar');
    const wrapper = document.getElementById('pageWrapper');
    if (!sidebar) return;

    const isCollapsed = localStorage.getItem(COLLAPSE_KEY) === '1';
    sidebar.classList.toggle('sidebar-collapsed', isCollapsed);
    if (wrapper) {
      wrapper.style.marginLeft = isCollapsed ? '64px' : '';
    }
  }

  window.toggleSidebarCollapse = function() {
    const sidebar  = document.getElementById('voxSidebar');
    const wrapper  = document.getElementById('pageWrapper');
    const overlay  = document.getElementById('sidebarOverlay');
    if (!sidebar) return;

    // 모바일에서 사이드바가 열려 있으면 그냥 닫기
    if (overlay && overlay.classList.contains('active')) {
      closeSidebar();
      return;
    }

    const collapsed = sidebar.classList.toggle('sidebar-collapsed');
    localStorage.setItem(COLLAPSE_KEY, collapsed ? '1' : '0');
    if (wrapper) {
      wrapper.style.marginLeft = collapsed ? '64px' : '';
    }
  };

  /* ---- Mobile open/close ---- */
  window.openSidebar = function() {
    const sidebar  = document.getElementById('voxSidebar');
    const overlay  = document.getElementById('sidebarOverlay');
    if (!sidebar) return;
    sidebar.classList.add('sidebar-open');
    if (overlay) overlay.classList.add('active');
    document.body.style.overflow = 'hidden';
  };

  window.closeSidebar = function() {
    const sidebar  = document.getElementById('voxSidebar');
    const overlay  = document.getElementById('sidebarOverlay');
    if (!sidebar) return;
    sidebar.classList.remove('sidebar-open');
    if (overlay) overlay.classList.remove('active');
    document.body.style.overflow = '';
  };

  /* ---- Theme toggle ---- */
  window.toggleTheme = function() {
    const html  = document.documentElement;
    const light = html.getAttribute('data-theme') === 'light';
    html.setAttribute('data-theme', light ? 'dark' : 'light');
    localStorage.setItem(THEME_KEY, light ? 'dark' : 'light');
  };

  /* ---- Auto-dismiss alerts ---- */
  function initAlerts() {
    const alerts = document.querySelectorAll('.alert-msg');
    alerts.forEach(function(el) {
      setTimeout(function() {
        el.style.transition = 'opacity 0.4s ease';
        el.style.opacity = '0';
        setTimeout(function() { el.remove(); }, 400);
      }, 4000);
    });
  }

  /* ---- Active nav item ---- */
  function setActiveNav() {
    const path = window.location.pathname;
    document.querySelectorAll('.nav-item').forEach(function(link) {
      const href = link.getAttribute('href');
      if (href && href !== '#' && href !== 'javascript:void(0)') {
        link.classList.toggle('active', path === href || (href.length > 1 && path.startsWith(href)));
      }
    });
  }

  /* ---- notLogin helper ---- */
  window.notLogin = function() {
    window.location.href = '/login/';
  };

  /* ---- Drag scroll for sidebar scroll rows ---- */
  function initDragScroll() {
    document.querySelectorAll('.sidebar-scroll-row').forEach(function(el) {
      var isDown = false;
      var startX, scrollLeft;

      el.addEventListener('mousedown', function(e) {
        isDown = true;
        el.style.cursor = 'grabbing';
        startX = e.pageX - el.offsetLeft;
        scrollLeft = el.scrollLeft;
        e.preventDefault();
      });
      el.addEventListener('mouseleave', function() {
        isDown = false;
        el.style.cursor = 'grab';
      });
      el.addEventListener('mouseup', function() {
        isDown = false;
        el.style.cursor = 'grab';
      });
      el.addEventListener('mousemove', function(e) {
        if (!isDown) return;
        var x = e.pageX - el.offsetLeft;
        var walk = (x - startX) * 1.2;
        el.scrollLeft = scrollLeft - walk;
      });
      el.style.cursor = 'grab';
    });
  }

  /* ---- Init ---- */
  document.addEventListener('DOMContentLoaded', function() {
    applyCollapse();
    initAlerts();
    setActiveNav();
    initDragScroll();

    // ESC key closes mobile sidebar
    document.addEventListener('keydown', function(e) {
      if (e.key === 'Escape') closeSidebar();
    });

    // iOS Safari: touchstart on overlay to close sidebar
    var overlay = document.getElementById('sidebarOverlay');
    if (overlay) {
      overlay.addEventListener('touchstart', function(e) {
        e.preventDefault();
        closeSidebar();
      }, { passive: false });
    }
  });

  // Apply theme immediately (before DOMContentLoaded to avoid flash)
  (function() {
    const saved = localStorage.getItem(THEME_KEY);
    if (saved) document.documentElement.setAttribute('data-theme', saved);
  })();
})();
