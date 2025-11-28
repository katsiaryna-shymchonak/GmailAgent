/**
 * DOM utility functions
 */
export class DOMUtils {
  static getVar(variable) {
    return getComputedStyle(document.body).getPropertyValue(variable).trim();
  }

  static setListLoading(spinner, isLoading) {
    if (spinner) {
      spinner.style.display = isLoading ? 'block' : 'none';
    }
  }
}
