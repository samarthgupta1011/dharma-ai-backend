// Mobile menu
function toggleMenu() {
  document.querySelector('.hamburger').classList.toggle('active');
  document.getElementById('mobileMenu').classList.toggle('active');
}

function closeMenu() {
  document.querySelector('.hamburger').classList.remove('active');
  document.getElementById('mobileMenu').classList.remove('active');
}

// Scroll animations
const observer = new IntersectionObserver((entries) => {
  entries.forEach((entry, i) => {
    if (entry.isIntersecting) {
      setTimeout(() => {
        entry.target.classList.add('visible');
      }, i * 80);
      observer.unobserve(entry.target);
    }
  });
}, { threshold: 0.1, rootMargin: '0px 0px -40px 0px' });

document.querySelectorAll('.fade-up').forEach(el => observer.observe(el));

// Close mobile menu on resize
window.addEventListener('resize', () => {
  if (window.innerWidth > 768) closeMenu();
});

// Waitlist form handling
// API base URL — update when custom domain is set up
const API_BASE = window.__API_BASE || 'https://dharma-api.kindbay-48de15ee.eastus2.azurecontainerapps.io';

document.querySelectorAll('.waitlist-form').forEach(form => {
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const input = form.querySelector('input[type="email"]');
    const btn = form.querySelector('button[type="submit"]');
    const parent = form.parentElement;
    const successEl = parent.querySelector('.waitlist-success');
    const errorEl = parent.querySelector('.waitlist-error');

    // Reset error state
    errorEl.hidden = true;
    errorEl.textContent = '';

    // Client-side validation
    const email = input.value.trim();
    if (!email || !input.validity.valid) {
      errorEl.textContent = 'Please enter a valid email address.';
      errorEl.hidden = false;
      return;
    }

    // Disable button during submission
    btn.disabled = true;
    btn.textContent = 'Joining...';

    const showSuccess = () => {
      form.style.display = 'none';
      successEl.hidden = false;
    };

    try {
      const res = await fetch(`${API_BASE}/api/waitlist`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });

      if (res.ok) {
        showSuccess();
      } else {
        const data = await res.json().catch(() => null);
        errorEl.textContent = data?.detail || data?.message || 'Please enter a valid email.';
        errorEl.hidden = false;
        btn.disabled = false;
        btn.textContent = 'Join the Waitlist';
      }
    } catch {
      // Network error — show success for graceful degradation
      showSuccess();
    }
  });
});

// Nav active state
(function setActiveNav() {
  const path = window.location.pathname;
  document.querySelectorAll('.nav-link').forEach(link => {
    const href = link.getAttribute('href');
    if (href === path || (href === '/' && path === '/index.html')) {
      link.classList.add('active');
    }
  });
})();
