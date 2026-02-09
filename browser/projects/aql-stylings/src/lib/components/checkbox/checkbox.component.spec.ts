import { ComponentFixture, TestBed } from '@angular/core/testing';

import { AqlCheckboxComponent } from './checkbox.component';

describe('AqlCheckboxComponent', () => {
  let component: AqlCheckboxComponent;
  let fixture: ComponentFixture<AqlCheckboxComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AqlCheckboxComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(AqlCheckboxComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
