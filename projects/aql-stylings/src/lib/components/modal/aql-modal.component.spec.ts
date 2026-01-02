import { ComponentFixture, TestBed } from '@angular/core/testing';
import { AqlModalComponent } from './aql-modal.component';
import { DebugElement } from '@angular/core';
import { By } from '@angular/platform-browser';

describe('AqlModalComponent', () => {
  let component: AqlModalComponent;
  let fixture: ComponentFixture<AqlModalComponent>;
  let dialogElement: DebugElement;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AqlModalComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(AqlModalComponent);
    component = fixture.componentInstance;
    dialogElement = fixture.debugElement.query(By.css('dialog'));
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should render a dialog element', () => {
    expect(dialogElement).toBeTruthy();
    expect(dialogElement.nativeElement.tagName).toBe('DIALOG');
  });

  it('should apply modal class', () => {
    expect(dialogElement.nativeElement.classList.contains('modal')).toBe(true);
  });

  it('should open and close modal', () => {
    expect(component.isOpen()).toBe(false);

    component.open();
    expect(component.isOpen()).toBe(true);

    component.close();
    expect(component.isOpen()).toBe(false);
  });

  it('should render title when provided', () => {
    fixture.componentRef.setInput('modalTitle', 'Test Modal');
    fixture.detectChanges();

    const title = dialogElement.query(By.css('h3'));
    expect(title).toBeTruthy();
    expect(title.nativeElement.textContent).toBe('Test Modal');
  });
});
