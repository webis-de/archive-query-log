import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TranslateModule } from '@ngx-translate/core';
import { AqlDropdownComponent, AqlButtonComponent } from 'aql-stylings';
import { LanguageService } from '../../services/language.service';

@Component({
  selector: 'app-language-selector',
  standalone: true,
  imports: [CommonModule, TranslateModule, AqlDropdownComponent, AqlButtonComponent],
  templateUrl: './language-selector.component.html',
  styleUrl: './language-selector.component.css',
})
export class LanguageSelectorComponent {
  readonly languageService = inject(LanguageService);

  onLanguageSelect(langCode: string): void {
    this.languageService.setLanguage(langCode);
  }
}
