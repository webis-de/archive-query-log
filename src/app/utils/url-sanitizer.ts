/**
 * URL Sanitizer Utility
 *
 * Provides functionality to strip tracking and interface parameters from URLs
 * for privacy-preserving purposes.
 */

/**
 * Common tracking parameters used by various platforms and analytics services.
 * This list is not exhaustive but covers the most common tracking parameters.
 */
export const TRACKING_PARAMETERS = new Set<string>([
  // Google Analytics / Ads
  'utm_source',
  'utm_medium',
  'utm_campaign',
  'utm_term',
  'utm_content',
  'gclid',
  'gclsrc',
  'dclid',
  'gbraid',
  'wbraid',

  // Facebook / Meta
  'fbclid',
  'fb_action_ids',
  'fb_action_types',
  'fb_source',
  'fb_ref',

  // Microsoft / Bing
  'msclkid',
  'form',
  'cvid',
  'sp',
  'refig',
  'pq',
  'sc',
  'qs',
  'sk',

  // Twitter / X
  'twclid',

  // TikTok
  'ttclid',

  // LinkedIn
  'lipi',
  'licu',
  'trk',

  // Reddit
  'rdt_cid',

  // Pinterest
  'epik',

  // Snapchat
  'ScCid',

  // Generic tracking
  'ref',
  'ref_src',
  'ref_url',
  'source',
  'campaign',
  'affiliate',
  'partner',

  // Analytics
  '_ga',
  '_gl',
  '_hsenc',
  '_hsmi',
  'mc_cid',
  'mc_eid',

  // A/B Testing & Injection (like in the example)
  'ase_injection_interface',
  'ase_injection_wipe',

  // App/Device parameters
  'app',
  'app_version',
  'app_name',
  'device',
  'device_type',
  'platform',
  'os_version',

  // Email tracking
  'vero_id',
  'vero_conv',
  '_ke',

  // Marketing automation
  'mkt_tok',
  'elqTrackId',
  'elqTrack',
  'assetType',
  'assetId',
  'recipientId',
  'campaignId',
  'siteId',

  // Session/User tracking
  'sid',
  'session_id',
  'visitor_id',
  'user_id',
  'tracking_id',

  // Misc tracking
  'trk',
  'tracking',
  'track',
  'clickid',
  'click_id',
]);

/**
 * Strips tracking and interface parameters from a URL.
 *
 * @param url - The URL to sanitize (can be a string or URL object)
 * @returns The sanitized URL string, or the original URL if parsing fails
 *
 * @example
 * stripTrackingParams('https://www.youtube.com/results?app=desktop&search_query=COVID&ase_injection_interface=mobile_iphone12pro')
 * // Returns: 'https://www.youtube.com/results?search_query=COVID'
 */
export function stripTrackingParams(url: string | URL): string {
  try {
    const urlObj = typeof url === 'string' ? new URL(url) : url;
    const cleanParams = new URLSearchParams();

    urlObj.searchParams.forEach((value, key) => {
      const keyLower = key.toLowerCase();
      if (!TRACKING_PARAMETERS.has(keyLower)) {
        cleanParams.append(key, value);
      }
    });

    // Rebuild URL with clean parameters
    const cleanUrl = new URL(urlObj.href);
    cleanUrl.search = cleanParams.toString();

    return cleanUrl.toString();
  } catch {
    // If URL parsing fails, return the original
    return typeof url === 'string' ? url : url.toString();
  }
}

/**
 * Gets the list of tracking parameters found in a URL.
 *
 * @param url - The URL to analyze
 * @returns Array of tracking parameter names found in the URL
 */
export function getTrackingParams(url: string | URL): string[] {
  try {
    const urlObj = typeof url === 'string' ? new URL(url) : url;
    const trackingParams: string[] = [];

    urlObj.searchParams.forEach((_, key) => {
      const keyLower = key.toLowerCase();
      if (TRACKING_PARAMETERS.has(keyLower)) {
        trackingParams.push(key);
      }
    });

    return trackingParams;
  } catch {
    return [];
  }
}

/**
 * Checks if a URL contains any tracking parameters.
 *
 * @param url - The URL to check
 * @returns True if the URL contains tracking parameters
 */
export function hasTrackingParams(url: string | URL): boolean {
  return getTrackingParams(url).length > 0;
}
