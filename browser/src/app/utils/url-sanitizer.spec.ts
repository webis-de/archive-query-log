import {
  stripTrackingParams,
  getTrackingParams,
  hasTrackingParams,
  TRACKING_PARAMETERS,
} from './url-sanitizer';

describe('URL Sanitizer', () => {
  describe('stripTrackingParams', () => {
    it('should remove tracking parameters from YouTube URL', () => {
      const url =
        'https://www.youtube.com/results?app=desktop&search_query=COVID&ase_injection_interface=mobile_iphone12pro&ase_injection_wipe=true';
      const result = stripTrackingParams(url);
      expect(result).toBe('https://www.youtube.com/results?search_query=COVID');
    });

    it('should remove UTM parameters', () => {
      const url =
        'https://example.com/page?utm_source=google&utm_medium=cpc&utm_campaign=summer&content=article';
      const result = stripTrackingParams(url);
      expect(result).toBe('https://example.com/page?content=article');
    });

    it('should remove Facebook click ID', () => {
      const url = 'https://example.com/page?fbclid=abc123&product=shoes';
      const result = stripTrackingParams(url);
      expect(result).toBe('https://example.com/page?product=shoes');
    });

    it('should remove Google click ID', () => {
      const url = 'https://example.com/page?gclid=xyz789&category=electronics';
      const result = stripTrackingParams(url);
      expect(result).toBe('https://example.com/page?category=electronics');
    });

    it('should preserve all parameters when no tracking params exist', () => {
      const url = 'https://example.com/search?q=test&page=1&sort=date';
      const result = stripTrackingParams(url);
      expect(result).toBe('https://example.com/search?q=test&page=1&sort=date');
    });

    it('should handle URLs without query parameters', () => {
      const url = 'https://example.com/page';
      const result = stripTrackingParams(url);
      expect(result).toBe('https://example.com/page');
    });

    it('should return original string for invalid URLs', () => {
      const url = 'not-a-valid-url';
      const result = stripTrackingParams(url);
      expect(result).toBe('not-a-valid-url');
    });

    it('should handle URL objects', () => {
      const url = new URL('https://example.com/page?utm_source=test&content=article');
      const result = stripTrackingParams(url);
      expect(result).toBe('https://example.com/page?content=article');
    });

    it('should preserve fragment', () => {
      const url = 'https://example.com/page?utm_source=test&section=intro#heading';
      const result = stripTrackingParams(url);
      expect(result).toBe('https://example.com/page?section=intro#heading');
    });

    it('should be case-insensitive for parameter matching', () => {
      const url = 'https://example.com/page?UTM_SOURCE=test&content=article';
      const result = stripTrackingParams(url);
      expect(result).toBe('https://example.com/page?content=article');
    });
  });

  describe('getTrackingParams', () => {
    it('should return list of tracking parameters found', () => {
      const url = 'https://example.com/page?utm_source=google&utm_medium=cpc&content=article';
      const result = getTrackingParams(url);
      expect(result).toEqual(['utm_source', 'utm_medium']);
    });

    it('should return empty array when no tracking params exist', () => {
      const url = 'https://example.com/page?q=test&page=1';
      const result = getTrackingParams(url);
      expect(result).toEqual([]);
    });

    it('should return empty array for invalid URLs', () => {
      const url = 'not-a-valid-url';
      const result = getTrackingParams(url);
      expect(result).toEqual([]);
    });
  });

  describe('hasTrackingParams', () => {
    it('should return true when tracking params exist', () => {
      const url = 'https://example.com/page?utm_source=google&content=article';
      expect(hasTrackingParams(url)).toBe(true);
    });

    it('should return false when no tracking params exist', () => {
      const url = 'https://example.com/page?q=test&page=1';
      expect(hasTrackingParams(url)).toBe(false);
    });

    it('should return false for invalid URLs', () => {
      const url = 'not-a-valid-url';
      expect(hasTrackingParams(url)).toBe(false);
    });
  });

  describe('TRACKING_PARAMETERS', () => {
    it('should contain common tracking parameters', () => {
      expect(TRACKING_PARAMETERS.has('utm_source')).toBe(true);
      expect(TRACKING_PARAMETERS.has('utm_medium')).toBe(true);
      expect(TRACKING_PARAMETERS.has('fbclid')).toBe(true);
      expect(TRACKING_PARAMETERS.has('gclid')).toBe(true);
      expect(TRACKING_PARAMETERS.has('ase_injection_interface')).toBe(true);
    });

    it('should not contain legitimate parameters', () => {
      expect(TRACKING_PARAMETERS.has('q')).toBe(false);
      expect(TRACKING_PARAMETERS.has('search_query')).toBe(false);
      expect(TRACKING_PARAMETERS.has('page')).toBe(false);
    });
  });
});
