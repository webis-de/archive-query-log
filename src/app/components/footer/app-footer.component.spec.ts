import { ComponentFixture, TestBed } from '@angular/core/testing';
import { AppFooterComponent } from './app-footer.component';
import { provideRouter } from '@angular/router';
import { By } from '@angular/platform-browser';
import { AqlInputFieldComponent, AqlButtonComponent } from 'aql-stylings';

describe('AppFooterComponent', () => {
  let component: AppFooterComponent;
  let fixture: ComponentFixture<AppFooterComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AppFooterComponent],
      providers: [provideRouter([])],
    }).compileComponents();

    fixture = TestBed.createComponent(AppFooterComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should render the custom input field for contact', () => {
    const inputField = fixture.debugElement.query(By.directive(AqlInputFieldComponent));
    expect(inputField).toBeTruthy();

    // Prüfen ob Placeholder korrekt (Englisch) ist
    expect(inputField.componentInstance.placeholder).toBe('Your email address');
    expect(inputField.componentInstance.icon).toContain('envelope');
  });

  it('should render the custom button for sending', () => {
    const button = fixture.debugElement.query(By.directive(AqlButtonComponent));
    expect(button).toBeTruthy();

    // Prüfen ob Label "Send" ist (via ng-content Projektion oder Property, je nach Button-Impl)
    // Da AqlButtonComponent ng-content nutzt, prüfen wir das native Element Text
    expect(button.nativeElement.textContent).toContain('Send');
  });

  it('should have "Get in touch" label', () => {
    const label = fixture.debugElement.query(By.css('.label-text'));
    expect(label.nativeElement.textContent).toContain('Get in touch');
  });

  it('should update signal on input', () => {
    const testEmail = 'test@example.com';
    component.contactEmail.set(testEmail);
    expect(component.contactEmail()).toBe(testEmail);
  });
});
