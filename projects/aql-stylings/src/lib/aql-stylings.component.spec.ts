import { TestBed } from '@angular/core/testing';
import { AqlStylingsComponent } from './aql-stylings.component';

describe('AqlStylingsComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AqlStylingsComponent],
    }).compileComponents();
  });

  it('should create', () => {
    const fixture = TestBed.createComponent(AqlStylingsComponent);
    const component = fixture.componentInstance;
    expect(component).toBeTruthy();
  });
});
