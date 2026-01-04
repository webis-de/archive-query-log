import { ComponentFixture, TestBed } from '@angular/core/testing';
import { AqlLineChartComponent } from './aql-line-chart.component';

describe('AqlLineChartComponent', () => {
  let component: AqlLineChartComponent;
  let fixture: ComponentFixture<AqlLineChartComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AqlLineChartComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(AqlLineChartComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
