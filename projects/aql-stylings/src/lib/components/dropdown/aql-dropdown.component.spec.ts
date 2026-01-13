import { Component } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { AqlDropdownComponent, DropdownPosition } from './aql-dropdown.component';

@Component({
  standalone: true,
  imports: [AqlDropdownComponent],
  template: `
    <aql-dropdown
      [position]="position"
      [matchTriggerWidth]="matchTriggerWidth"
      [contentWidth]="contentWidth"
      [open]="open"
    >
      <button trigger type="button" class="btn">Toggle</button>
      <ul content>
        <li><a>Item 1</a></li>
      </ul>
    </aql-dropdown>
  `,
})
class DropdownHostComponent {
  position: DropdownPosition | undefined = 'bottom';
  matchTriggerWidth = false;
  contentWidth: string | null = '14rem';
  open?: boolean = undefined;
}

describe('AqlDropdownComponent', () => {
  let fixture: ComponentFixture<DropdownHostComponent>;
  let host: DropdownHostComponent;
  let dropdownElement: HTMLElement;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [DropdownHostComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(DropdownHostComponent);
    host = fixture.componentInstance;
    fixture.detectChanges();

    const dropdownDebug = fixture.debugElement.query(By.directive(AqlDropdownComponent));
    dropdownElement = dropdownDebug.nativeElement as HTMLElement;
  });

  function getDropdownContent(): HTMLElement | null {
    return dropdownElement.querySelector('div.dropdown-content') as HTMLElement;
  }

  it('should render trigger and content containers', () => {
    expect(dropdownElement).toBeTruthy();
    expect(dropdownElement.querySelector('[trigger]')).toBeTruthy();
    expect(getDropdownContent()).toBeTruthy();
  });

  it('should apply position classes based on input', () => {
    host.position = 'top start';
    fixture.detectChanges();

    expect(dropdownElement.classList.contains('dropdown-top')).toBe(true);
    expect(dropdownElement.classList.contains('dropdown-start')).toBe(true);
    expect(dropdownElement.classList.contains('dropdown-bottom')).toBe(false);
  });

  it('should toggle open state when trigger is clicked and close on outside click', () => {
    const trigger = dropdownElement.querySelector('[trigger]') as HTMLElement;
    trigger.click();
    fixture.detectChanges();

    expect(dropdownElement.classList.contains('dropdown-open')).toBe(true);

    document.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    fixture.detectChanges();

    expect(dropdownElement.classList.contains('dropdown-open')).toBe(false);
  });

  it('should respect the open input value', () => {
    host.open = true;
    fixture.detectChanges();
    expect(dropdownElement.classList.contains('dropdown-open')).toBe(true);

    host.open = false;
    fixture.detectChanges();
    expect(dropdownElement.classList.contains('dropdown-open')).toBe(false);
  });

  it('should apply matchTriggerWidth class and clear inline width when enabled', () => {
    host.matchTriggerWidth = true;
    fixture.detectChanges();

    const dropdownContent = getDropdownContent();
    expect(dropdownContent!.classList.contains('w-full')).toBe(true);

    host.matchTriggerWidth = false;
    fixture.detectChanges();
    expect(dropdownContent!.classList.contains('w-full')).toBe(false);
  });

  it('should set inline width when contentWidth is provided and matchTriggerWidth is false', () => {
    host.matchTriggerWidth = false;
    host.contentWidth = '20rem';
    fixture.detectChanges();

    expect(getDropdownContent()!.style.width).toBe('20rem');

    host.matchTriggerWidth = true;
    fixture.detectChanges();
    expect(getDropdownContent()!.style.width).toBe('');
  });
});
