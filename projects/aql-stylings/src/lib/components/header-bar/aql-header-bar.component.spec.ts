import { ComponentFixture, TestBed } from '@angular/core/testing';
import { AqlHeaderBarComponent } from './aql-header-bar.component';

describe('AqlHeaderBarComponent', () => {
  let component: AqlHeaderBarComponent;
  let fixture: ComponentFixture<AqlHeaderBarComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AqlHeaderBarComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(AqlHeaderBarComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should render header bar element', () => {
    const compiled = fixture.nativeElement as HTMLElement;
    const headerBar = compiled.querySelector('.header-bar');
    expect(headerBar).toBeTruthy();
  });

  it('should have navbar class', () => {
    const compiled = fixture.nativeElement as HTMLElement;
    const headerBar = compiled.querySelector('.navbar');
    expect(headerBar).toBeTruthy();
  });

  it('should be sticky positioned', () => {
    const compiled = fixture.nativeElement as HTMLElement;
    const headerBar = compiled.querySelector('.sticky');
    expect(headerBar).toBeTruthy();
  });
});
