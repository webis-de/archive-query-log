import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ArchiveSearchViewComponent } from './archive-search-view.component';
import { TranslateModule } from '@ngx-translate/core';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { ArchiveService } from '../../services/archive.service';

describe('ArchiveSearchViewComponent', () => {
  let component: ArchiveSearchViewComponent;
  let fixture: ComponentFixture<ArchiveSearchViewComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ArchiveSearchViewComponent, TranslateModule.forRoot()],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        ArchiveService, // explicit provider if needed, or rely on root injectable
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(ArchiveSearchViewComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
