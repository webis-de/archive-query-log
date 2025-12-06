import { ComponentFixture, TestBed } from '@angular/core/testing';
import { AppFooterComponent } from './app-footer.component';
import { provideRouter } from '@angular/router';
import { By } from '@angular/platform-browser';

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

  it('should render copyright year', () => {
    const year = new Date().getFullYear().toString();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.textContent).toContain(year);
  });

  it('should render the SWEP identifier', () => {
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.textContent).toContain('SWEP 2025');
  });

  it('should render imprint and privacy links', () => {
    const links = fixture.debugElement.queryAll(By.css('a'));
    const linkTexts = links.map(l => l.nativeElement.textContent);

    expect(linkTexts).toContain('Imprint');
    expect(linkTexts).toContain('Privacy Policy');
  });
});
