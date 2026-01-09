import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  OnDestroy,
  computed,
  input,
  output,
  signal,
  viewChild,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { AqlButtonComponent } from '../button/aql-button.component';

export type ModalPosition = 'top' | 'middle' | 'bottom';
export type ModalAlign = 'start' | 'center' | 'end';

@Component({
  selector: 'aql-modal',
  standalone: true,
  imports: [CommonModule, AqlButtonComponent],
  templateUrl: './aql-modal.component.html',
  styleUrl: './aql-modal.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AqlModalComponent implements OnDestroy {
  dialogElement = viewChild<ElementRef<HTMLDialogElement>>('dialogElement');
  modalTitle = input<string>();
  position = input<ModalPosition>('middle');
  align = input<ModalAlign>('center');
  responsive = input(false);
  closeOnBackdropClick = input(true);
  closeOnEscape = input(true);
  showCloseButton = input(true);
  maxWidth = input<'sm' | 'md' | 'lg' | 'xl' | 'full'>('lg');
  modalOpen = output<void>();
  modalClose = output<void>();
  isOpen = signal(false);
  modalClasses = computed(() => {
    const classes: string[] = ['modal'];

    if (this.responsive()) {
      classes.push(`modal-bottom sm:modal-${this.position()}`);
    } else {
      if (this.position() !== 'middle') {
        classes.push(`modal-${this.position()}`);
      }
    }

    if (this.align() !== 'center') {
      classes.push(`modal-${this.align()}`);
    }

    return classes.join(' ');
  });
  modalBoxClasses = computed(() => {
    const classes: string[] = ['modal-box'];

    switch (this.maxWidth()) {
      case 'sm':
        classes.push('max-w-sm');
        break;
      case 'md':
        classes.push('max-w-md');
        break;
      case 'lg':
        classes.push('max-w-lg');
        break;
      case 'xl':
        classes.push('max-w-xl');
        break;
      case 'full':
        classes.push('max-w-full');
        break;
    }

    return classes.join(' ');
  });

  private cancelHandler?: (event: Event) => void;

  ngOnDestroy(): void {
    this.detachCancelHandler();
    this.close();
  }

  open(): void {
    const dialog = this.dialogElement()?.nativeElement;
    if (dialog) {
      dialog.showModal();
      this.isOpen.set(true);
      this.modalOpen.emit();

      if (!this.closeOnEscape()) {
        this.detachCancelHandler();
        this.cancelHandler = (event: Event) => event.preventDefault();
        dialog.addEventListener('cancel', this.cancelHandler);
      }
    }
  }

  close(): void {
    const dialog = this.dialogElement()?.nativeElement;
    if (dialog && dialog.open) {
      dialog.close();
      this.isOpen.set(false);
      this.modalClose.emit();
    }
    this.detachCancelHandler();
  }

  onBackdropClick(event: MouseEvent): void {
    if (!this.closeOnBackdropClick()) {
      return;
    }

    const dialog = this.dialogElement()?.nativeElement;
    if (dialog && event.target === dialog) {
      const rect = dialog.getBoundingClientRect();
      const isInDialog =
        rect.top <= event.clientY &&
        event.clientY <= rect.top + rect.height &&
        rect.left <= event.clientX &&
        event.clientX <= rect.left + rect.width;

      if (!isInDialog) {
        this.close();
      }
    }
  }

  private detachCancelHandler(): void {
    const dialog = this.dialogElement()?.nativeElement;
    if (dialog && this.cancelHandler) {
      dialog.removeEventListener('cancel', this.cancelHandler);
      this.cancelHandler = undefined;
    }
  }
}
