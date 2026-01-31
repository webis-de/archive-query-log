import { ComponentFixture, TestBed } from '@angular/core/testing';
import { MetadataWebsiteTabComponent } from './metadata-website-tab.component';
import { TranslateModule } from '@ngx-translate/core';

describe('MetadataWebsiteTabComponent', () => {
  let component: MetadataWebsiteTabComponent;
  let fixture: ComponentFixture<MetadataWebsiteTabComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [MetadataWebsiteTabComponent, TranslateModule.forRoot()],
    }).compileComponents();

    fixture = TestBed.createComponent(MetadataWebsiteTabComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
