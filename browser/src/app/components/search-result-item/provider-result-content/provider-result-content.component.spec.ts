import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ProviderResultContentComponent } from './provider-result-content.component';
import { TranslateModule } from '@ngx-translate/core';

describe('ProviderResultContentComponent', () => {
  let component: ProviderResultContentComponent;
  let fixture: ComponentFixture<ProviderResultContentComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ProviderResultContentComponent, TranslateModule.forRoot()],
    }).compileComponents();

    fixture = TestBed.createComponent(ProviderResultContentComponent);
    component = fixture.componentInstance;
    fixture.componentRef.setInput('provider', { name: 'Test', id: '1', priority: 1 });
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
