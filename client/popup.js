/**
 * Main entry point - initializes the application
 */
import { App } from './js/core/App.js';

document.addEventListener('DOMContentLoaded', () => {
  try {
    new App();
  } catch (err) {
    console.error('App bootstrap failed:', err);
    const log = document.getElementById('conversation-log');
    if (log) {
      log.textContent = `Failed to start app: ${err.message}`;
    }
  }
});

window.addEventListener('error', (e) => {
  console.error('Global error:', e.message, e.error);
});
window.addEventListener('unhandledrejection', (e) => {
  console.error('Unhandled promise rejection:', e.reason);
});
