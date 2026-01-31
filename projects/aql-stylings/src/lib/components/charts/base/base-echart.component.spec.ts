import { Component } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { BaseEChartComponent } from './base-echart.component';

@Component({
  template: '<div #chartContainer style="width: 100px; height: 100px;"></div>',
  standalone: true,
})
class TestChartComponent extends BaseEChartComponent {
  protected buildDefaultOption() {
    return { title: { text: 'Test' } };
  }
}

describe('BaseEChartComponent', () => {
  let component: TestChartComponent;
  let fixture: ComponentFixture<TestChartComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [TestChartComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(TestChartComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
