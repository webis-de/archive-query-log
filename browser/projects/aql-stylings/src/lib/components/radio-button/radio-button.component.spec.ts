import { ComponentFixture, TestBed } from '@angular/core/testing';

import { AqlRadioButtonComponent } from './radio-button.component';

describe('AqlRadioButtonComponent', () => {
  let component: AqlRadioButtonComponent;
  let fixture: ComponentFixture<AqlRadioButtonComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AqlRadioButtonComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(AqlRadioButtonComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
