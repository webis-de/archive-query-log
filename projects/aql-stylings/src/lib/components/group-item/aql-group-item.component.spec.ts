import { ComponentFixture, TestBed } from '@angular/core/testing';
import { AqlGroupItemComponent } from './aql-group-item.component';

describe('AqlGroupItemComponent', () => {
  let component: AqlGroupItemComponent;
  let fixture: ComponentFixture<AqlGroupItemComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AqlGroupItemComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(AqlGroupItemComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should start in closed state', () => {
    expect(component.open()).toBe(false);
  });

  it('should compute correct icon based on open state', () => {
    fixture.componentRef.setInput('iconBefore', 'bi-folder');
    fixture.componentRef.setInput('iconBeforeOpen', 'bi-folder-open');
    fixture.detectChanges();

    expect(component.computedIconBefore()).toBe('bi-folder');

    component.open.set(true);
    expect(component.computedIconBefore()).toBe('bi-folder-open');
  });

  it('should return iconBefore when iconBeforeOpen is not set', () => {
    fixture.componentRef.setInput('iconBefore', 'bi-folder');
    fixture.detectChanges();

    component.open.set(true);
    expect(component.computedIconBefore()).toBe('bi-folder');
  });

  it('should handle toggle event', () => {
    const mockEvent = {
      target: { open: true } as HTMLDetailsElement,
    } as unknown as Event;

    component.onToggle(mockEvent);
    expect(component.open()).toBe(true);
  });

  it('should prevent default when clicking after slot', () => {
    const mockAfterSlot = document.createElement('div');
    mockAfterSlot.classList.add('after-slot');

    const mockEvent = {
      target: mockAfterSlot,
      preventDefault: jasmine.createSpy('preventDefault'),
    } as unknown as MouseEvent;

    component.onSummaryClick(mockEvent);
    expect(mockEvent.preventDefault).toHaveBeenCalled();
  });
});
