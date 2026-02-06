import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ProviderSearchViewComponent } from './provider-search-view.component';
import { TranslateModule } from '@ngx-translate/core';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { ProviderService } from '../../services/provider.service';

describe('ProviderSearchViewComponent', () => {
  let component: ProviderSearchViewComponent;
  let fixture: ComponentFixture<ProviderSearchViewComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ProviderSearchViewComponent, TranslateModule.forRoot()],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        ProviderService, // explicit provider if needed
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(ProviderSearchViewComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
