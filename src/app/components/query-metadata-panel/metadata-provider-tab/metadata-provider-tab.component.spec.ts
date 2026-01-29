import { ComponentFixture, TestBed } from '@angular/core/testing';
import { MetadataProviderTabComponent } from './metadata-provider-tab.component';
import { TranslateModule } from '@ngx-translate/core';

describe('MetadataProviderTabComponent', () => {
  let component: MetadataProviderTabComponent;
  let fixture: ComponentFixture<MetadataProviderTabComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [MetadataProviderTabComponent, TranslateModule.forRoot()],
    }).compileComponents();

    fixture = TestBed.createComponent(MetadataProviderTabComponent);
    component = fixture.componentInstance;
    fixture.componentRef.setInput('providerDetail', null);
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
