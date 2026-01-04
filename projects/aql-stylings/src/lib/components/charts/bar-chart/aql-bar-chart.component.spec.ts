import { ComponentFixture, TestBed } from '@angular/core/testing';
import { AqlBarChartComponent } from './aql-bar-chart.component';

describe('AqlBarChartComponent', () => {
  let component: AqlBarChartComponent;
  let fixture: ComponentFixture<AqlBarChartComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AqlBarChartComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(AqlBarChartComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
