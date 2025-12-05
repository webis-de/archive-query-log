import { ChangeDetectionStrategy, Component, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
// WICHTIG: Import deiner Komponenten
import { AqlInputFieldComponent, AqlButtonComponent } from 'aql-stylings';

@Component({
  selector: 'app-footer',
  standalone: true,
  imports: [CommonModule, RouterLink, FormsModule, AqlInputFieldComponent, AqlButtonComponent],
  templateUrl: './app-footer.component.html',
  styleUrl: './app-footer.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AppFooterComponent {
  readonly currentYear = signal(new Date().getFullYear());

  readonly contactEmail = signal('');
  readonly contactMessage = signal('');

  // Einfache Validierung: Beide Felder müssen Inhalt haben
  readonly isValid = computed(
    () => this.contactEmail().length > 0 && this.contactMessage().length > 0,
  );

  onContactSubmit(): void {
    if (this.isValid()) {
      console.log('Form submitted:', {
        email: this.contactEmail(),
        message: this.contactMessage(),
      });

      // Reset
      this.contactEmail.set('');
      this.contactMessage.set('');
    }
  }
}
