import { MissingTranslationHandler, MissingTranslationHandlerParams } from '@ngx-translate/core';

/**
 * Custom handler for missing translations
 * Logs warnings to console when a translation key is missing
 */
export class CustomMissingTranslationHandler implements MissingTranslationHandler {
  handle(params: MissingTranslationHandlerParams): string {
    console.warn(`Missing translation for key: ${params.key}`);

    // Return the key itself as fallback
    return params.key;
  }
}
