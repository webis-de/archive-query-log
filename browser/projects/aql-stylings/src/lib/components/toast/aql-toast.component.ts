import { Component, inject, ChangeDetectionStrategy, Signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ToastService, ToastType, Toast } from '../../services/toast.service';

@Component({
  selector: 'aql-toast',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './aql-toast.component.html',
  styleUrl: './aql-toast.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AqlToastComponent {
  readonly toasts: Signal<Toast[]>;

  private readonly toastService = inject(ToastService);

  constructor() {
    this.toasts = this.toastService.toasts;
  }

  getAlertClass(type: ToastType): string {
    switch (type) {
      case 'info':
        return 'alert-info';
      case 'success':
        return 'alert-success';
      case 'warning':
        return 'alert-warning';
      case 'error':
        return 'alert-error';
      default:
        return 'alert-info';
    }
  }
}
