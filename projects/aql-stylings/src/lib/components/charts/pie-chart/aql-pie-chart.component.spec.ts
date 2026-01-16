import { ComponentFixture, TestBed } from '@angular/core/testing';
import { AqlPieChartComponent } from './aql-pie-chart.component';

describe('AqlPieChartComponent', () => {
  let component: AqlPieChartComponent;
  let fixture: ComponentFixture<AqlPieChartComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AqlPieChartComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(AqlPieChartComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
