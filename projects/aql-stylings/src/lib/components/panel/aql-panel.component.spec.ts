import { ComponentFixture, TestBed } from '@angular/core/testing';
import { AqlPanelComponent } from './aql-panel.component';

describe('AqlPanelComponent', () => {
  let component: AqlPanelComponent;
  let fixture: ComponentFixture<AqlPanelComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AqlPanelComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(AqlPanelComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should have default values for inputs', () => {
    expect(component.bordered()).toBe(true);
    expect(component.shadow()).toBe(false);
    expect(component.rounded()).toBe(true);
    expect(component.panelTitle()).toBeUndefined();
    expect(component.subtitle()).toBeUndefined();
  });

  it('should accept panelTitle input', () => {
    fixture.componentRef.setInput('panelTitle', 'Test Title');
    fixture.detectChanges();
    expect(component.panelTitle()).toBe('Test Title');
  });

  it('should accept subtitle input', () => {
    fixture.componentRef.setInput('subtitle', 'Test Subtitle');
    fixture.detectChanges();
    expect(component.subtitle()).toBe('Test Subtitle');
  });

  it('should accept bordered input', () => {
    fixture.componentRef.setInput('bordered', false);
    fixture.detectChanges();
    expect(component.bordered()).toBe(false);
  });

  it('should accept shadow input', () => {
    fixture.componentRef.setInput('shadow', true);
    fixture.detectChanges();
    expect(component.shadow()).toBe(true);
  });

  it('should accept rounded input', () => {
    fixture.componentRef.setInput('rounded', false);
    fixture.detectChanges();
    expect(component.rounded()).toBe(false);
  });
});
