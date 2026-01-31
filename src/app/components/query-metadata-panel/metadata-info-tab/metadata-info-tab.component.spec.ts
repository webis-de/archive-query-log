import { ComponentFixture, TestBed } from '@angular/core/testing';
import { MetadataInfoTabComponent } from './metadata-info-tab.component';
import { TranslateModule } from '@ngx-translate/core';
import { HttpClientTestingModule } from '@angular/common/http/testing';

describe('MetadataInfoTabComponent', () => {
  let component: MetadataInfoTabComponent;
  let fixture: ComponentFixture<MetadataInfoTabComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [MetadataInfoTabComponent, TranslateModule.forRoot(), HttpClientTestingModule],
    }).compileComponents();

    fixture = TestBed.createComponent(MetadataInfoTabComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
