import { ComponentFixture, TestBed } from '@angular/core/testing';

import { AqlInputFieldComponent } from './input-field.component';

describe('AqlInputFieldComponent', () => {
  let component: AqlInputFieldComponent;
  let fixture: ComponentFixture<AqlInputFieldComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AqlInputFieldComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(AqlInputFieldComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
