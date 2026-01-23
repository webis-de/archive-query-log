import { ComponentFixture, TestBed } from '@angular/core/testing';
import { MetadataRelatedTabComponent } from './metadata-related-tab.component';
import { TranslateModule } from '@ngx-translate/core';
import { HttpClientTestingModule } from '@angular/common/http/testing';

describe('MetadataRelatedTabComponent', () => {
  let component: MetadataRelatedTabComponent;
  let fixture: ComponentFixture<MetadataRelatedTabComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [MetadataRelatedTabComponent, TranslateModule.forRoot(), HttpClientTestingModule],
    }).compileComponents();

    fixture = TestBed.createComponent(MetadataRelatedTabComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
