import { Component, inject, input, ChangeDetectionStrategy } from '@angular/core';

import { TranslateModule } from '@ngx-translate/core';
import { AqlDropdownComponent, AqlButtonComponent, AqlTooltipDirective } from 'aql-stylings';
import { LanguageService } from '../../services/language.service';

@Component({
  selector: 'app-language-selector',
  standalone: true,
  imports: [TranslateModule, AqlDropdownComponent, AqlButtonComponent, AqlTooltipDirective],
  templateUrl: './language-selector.component.html',
  styleUrl: './language-selector.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class LanguageSelectorComponent {
  readonly languageService = inject(LanguageService);
  readonly showLabel = input<boolean>(true);
  readonly dropdownPosition = input<
    'left' | 'right' | 'top' | 'bottom' | 'end' | 'start' | 'right end' | 'right top'
  >('start');

  onLanguageSelect(langCode: string): void {
    this.languageService.setLanguage(langCode);
  }
}
