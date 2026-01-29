import { ComponentFixture, TestBed } from '@angular/core/testing';
import { AqlToastComponent } from './aql-toast.component';
import { ToastService } from '../../services/toast.service';

describe('AqlToastComponent', () => {
  let component: AqlToastComponent;
  let fixture: ComponentFixture<AqlToastComponent>;
  let toastService: ToastService;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AqlToastComponent],
      providers: [ToastService],
    }).compileComponents();

    fixture = TestBed.createComponent(AqlToastComponent);
    component = fixture.componentInstance;
    toastService = TestBed.inject(ToastService);
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should display toast when service has a toast', () => {
    toastService.show('Test Message', 'info');
    fixture.detectChanges();
    const toastElement = fixture.nativeElement.querySelector('.toast');
    expect(toastElement).toBeTruthy();
    expect(toastElement.textContent).toContain('Test Message');
  });

  it('should use correct alert class based on type', () => {
    toastService.show('Error Message', 'error');
    fixture.detectChanges();
    const alertElement = fixture.nativeElement.querySelector('.alert-error');
    expect(alertElement).toBeTruthy();
  });
});
