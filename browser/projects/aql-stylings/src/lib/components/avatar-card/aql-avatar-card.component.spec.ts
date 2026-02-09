import { ComponentFixture, TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { AqlAvatarCardComponent } from './aql-avatar-card.component';

describe('AqlAvatarCardComponent', () => {
  let fixture: ComponentFixture<AqlAvatarCardComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AqlAvatarCardComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(AqlAvatarCardComponent);
    fixture.detectChanges();
  });

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  function setInput(name: string, value: any): void {
    fixture.componentRef.setInput(name, value);
    fixture.detectChanges();
  }

  it('should render provided name and subtitle', () => {
    setInput('name', 'Jane Doe');
    setInput('subtitle', 'Product Team');

    const nameEl = fixture.debugElement.query(By.css('.aql-avatar-card p.font-semibold'));
    const subtitleEl = fixture.debugElement.query(
      By.css('.aql-avatar-card p.text-base-content\\/60'),
    );

    expect(nameEl.nativeElement.textContent.trim()).toBe('Jane Doe');
    expect(subtitleEl.nativeElement.textContent.trim()).toBe('Product Team');
  });

  it('should render the avatar image when src is provided', () => {
    const mockSrc = 'https://example.com/avatar.png';
    setInput('imageSrc', mockSrc);
    setInput('imageAlt', 'Profile photo');

    const imgEl = fixture.debugElement.query(By.css('.aql-avatar-card img'));
    expect(imgEl).toBeTruthy();
    expect((imgEl.nativeElement as HTMLImageElement).src).toContain(mockSrc);
    expect((imgEl.nativeElement as HTMLImageElement).alt).toBe('Profile photo');
  });

  it('should fall back to initials when no image is provided', () => {
    setInput('imageSrc', null);
    setInput('name', 'Ada Lovelace');

    const fallback = fixture.debugElement.query(By.css('.aql-avatar-card .avatar .flex'));
    expect(fallback).toBeTruthy();
    expect(fallback.nativeElement.textContent.trim()).toBe('AL');
  });

  it('should expose hover/active-ready button styling', () => {
    const container = fixture.debugElement.query(By.css('button.aql-avatar-card'));
    expect(container).toBeTruthy();
    expect(container.nativeElement.classList.contains('hover:bg-base-200')).toBeTrue();
    expect(container.nativeElement.classList.contains('active:bg-base-300')).toBeTrue();
  });

  it('should render avatar with default size', () => {
    const avatarWrapper = fixture.debugElement.query(By.css('.aql-avatar-card .avatar > div'));
    expect(avatarWrapper).toBeTruthy();
    expect(avatarWrapper.nativeElement.classList.contains('w-8')).toBeTrue();
  });
});
