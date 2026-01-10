import { MissingTranslationHandler, MissingTranslationHandlerParams } from '@ngx-translate/core';

/**
 * Custom handler for missing translations
 * Suppresses warnings during initial app startup to avoid false positives
 */
export class CustomMissingTranslationHandler implements MissingTranslationHandler {
  private startupTime = Date.now();
  private readonly startupGracePeriod = 1000;

  handle(params: MissingTranslationHandlerParams): string {
    // Only log warnings after grace period to avoid false positives during initial load
    const timeSinceStartup = Date.now() - this.startupTime;
    if (timeSinceStartup > this.startupGracePeriod) {
      console.warn(`Missing translation for key: ${params.key}`);
    }

    // fallback
    return params.key;
  }
}
