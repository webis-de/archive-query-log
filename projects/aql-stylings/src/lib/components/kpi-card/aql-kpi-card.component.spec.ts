import { ComponentFixture, TestBed } from '@angular/core/testing';
import { AqlKpiCardComponent } from './aql-kpi-card.component';
import { DecimalPipe } from '@angular/common';

describe('AqlKpiCardComponent', () => {
  let component: AqlKpiCardComponent;
  let fixture: ComponentFixture<AqlKpiCardComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AqlKpiCardComponent, DecimalPipe],
    }).compileComponents();

    fixture = TestBed.createComponent(AqlKpiCardComponent);
    component = fixture.componentInstance;
    fixture.componentRef.setInput('title', 'Test KPI');
    fixture.componentRef.setInput('value', 100);
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
