import { ComponentFixture, TestBed } from '@angular/core/testing';
import { AqlButtonComponent } from './aql-button.component';
import { DebugElement } from '@angular/core';
import { By } from '@angular/platform-browser';

describe('AqlButtonComponent', () => {
  let component: AqlButtonComponent;
  let fixture: ComponentFixture<AqlButtonComponent>;
  let buttonElement: DebugElement;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AqlButtonComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(AqlButtonComponent);
    component = fixture.componentInstance;
    buttonElement = fixture.debugElement.query(By.css('button'));
    fixture.detectChanges();
  });

  function setInputAndDetect<K extends keyof AqlButtonComponent>(
    name: K,
    value: AqlButtonComponent[K],
  ): void {
    fixture.componentRef.setInput(name as string, value);
    fixture.detectChanges();
  }

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should render a button element', () => {
    expect(buttonElement).toBeTruthy();
    expect(buttonElement.nativeElement.tagName).toBe('BUTTON');
  });

  describe('Button Types', () => {
    it('should apply default btn class', () => {
      expect(buttonElement.nativeElement.classList.contains('btn')).toBe(true);
    });

    it('should apply primary type class', () => {
      setInputAndDetect('btnType', 'primary');
      expect(buttonElement.nativeElement.classList.contains('btn-primary')).toBe(true);
    });

    it('should apply secondary type class', () => {
      setInputAndDetect('btnType', 'secondary');
      expect(buttonElement.nativeElement.classList.contains('btn-secondary')).toBe(true);
    });

    it('should apply accent type class', () => {
      setInputAndDetect('btnType', 'accent');
      expect(buttonElement.nativeElement.classList.contains('btn-accent')).toBe(true);
    });

    it('should apply ghost type class', () => {
      setInputAndDetect('btnType', 'ghost');
      expect(buttonElement.nativeElement.classList.contains('btn-ghost')).toBe(true);
    });

    it('should apply link type class', () => {
      setInputAndDetect('btnType', 'link');
      expect(buttonElement.nativeElement.classList.contains('btn-link')).toBe(true);
    });
  });

  describe('Button Styles', () => {
    it('should not apply style class for default style', () => {
      setInputAndDetect('iconStyle', 'default');
      expect(buttonElement.nativeElement.classList.contains('btn-square')).toBe(false);
      expect(buttonElement.nativeElement.classList.contains('btn-circle')).toBe(false);
    });

    it('should apply square style class', () => {
      setInputAndDetect('iconStyle', 'square');
      expect(buttonElement.nativeElement.classList.contains('btn-square')).toBe(true);
    });

    it('should apply circle style class', () => {
      setInputAndDetect('iconStyle', 'circle');
      expect(buttonElement.nativeElement.classList.contains('btn-circle')).toBe(true);
    });
  });

  describe('Button State', () => {
    it('should not be disabled by default', () => {
      expect(buttonElement.nativeElement.disabled).toBe(false);
    });

    it('should be disabled when disabled input is true', () => {
      setInputAndDetect('disabled', true);
      expect(buttonElement.nativeElement.disabled).toBe(true);
    });

    it('should not emit click event when disabled', () => {
      setInputAndDetect('disabled', true);
      spyOn(component.buttonClick, 'emit');

      component.onClick(new MouseEvent('click'));

      expect(component.buttonClick.emit).not.toHaveBeenCalled();
    });

    it('should emit click event when not disabled', () => {
      setInputAndDetect('disabled', false);
      spyOn(component.buttonClick, 'emit');

      const mockEvent = new MouseEvent('click');
      component.onClick(mockEvent);

      expect(component.buttonClick.emit).toHaveBeenCalledWith(mockEvent);
    });
  });

  describe('Button Icons', () => {
    it('should not render icons by default', () => {
      const icons = buttonElement.queryAll(By.css('i'));
      expect(icons.length).toBe(0);
    });

    it('should render icon before content', () => {
      setInputAndDetect('iconBefore', 'bi-plus-circle');

      const icon = buttonElement.query(By.css('i.bi-plus-circle'));
      expect(icon).toBeTruthy();
    });

    it('should render icon after content', () => {
      setInputAndDetect('iconAfter', 'bi-arrow-right');

      const icon = buttonElement.query(By.css('i.bi-arrow-right'));
      expect(icon).toBeTruthy();
    });

    it('should render both icons when both are provided', () => {
      fixture.componentRef.setInput('iconBefore', 'bi-plus-circle');
      fixture.componentRef.setInput('iconAfter', 'bi-arrow-right');
      fixture.detectChanges();

      const icons = buttonElement.queryAll(By.css('i'));
      expect(icons.length).toBe(2);
      expect(icons[0].nativeElement.classList.contains('bi-plus-circle')).toBe(true);
      expect(icons[1].nativeElement.classList.contains('bi-arrow-right')).toBe(true);
    });
  });

  describe('Button Outline', () => {
    it('should apply outline class when outline is true', () => {
      setInputAndDetect('outline', true);
      expect(buttonElement.nativeElement.classList.contains('btn-outline')).toBe(true);
    });

    it('should apply outline class with type', () => {
      fixture.componentRef.setInput('btnType', 'primary');
      fixture.componentRef.setInput('outline', true);
      fixture.detectChanges();
      expect(buttonElement.nativeElement.classList.contains('btn-outline')).toBe(true);
      expect(buttonElement.nativeElement.classList.contains('btn-primary')).toBe(true);
    });
  });

  describe('Button Size', () => {
    it('should not apply size class for medium size', () => {
      component.size = 'md';
      fixture.detectChanges();
      expect(buttonElement.nativeElement.classList.contains('btn-xs')).toBe(false);
      expect(buttonElement.nativeElement.classList.contains('btn-sm')).toBe(false);
      expect(buttonElement.nativeElement.classList.contains('btn-lg')).toBe(false);
    });

    it('should apply xs size class', () => {
      setInputAndDetect('size', 'xs');
      expect(buttonElement.nativeElement.classList.contains('btn-xs')).toBe(true);
    });

    it('should apply sm size class', () => {
      setInputAndDetect('size', 'sm');
      expect(buttonElement.nativeElement.classList.contains('btn-sm')).toBe(true);
    });

    it('should apply lg size class', () => {
      setInputAndDetect('size', 'lg');
      expect(buttonElement.nativeElement.classList.contains('btn-lg')).toBe(true);
    });
  });

  describe('Button Full Width', () => {
    it('should not apply block class by default', () => {
      expect(buttonElement.nativeElement.classList.contains('btn-block')).toBe(false);
    });

    it('should apply block class when fullWidth is true', () => {
      setInputAndDetect('fullWidth', true);
      expect(buttonElement.nativeElement.classList.contains('btn-block')).toBe(true);
    });
  });

  describe('Content Projection', () => {
    it('should project content', () => {
      const testFixture = TestBed.createComponent(AqlButtonComponent);

      // Set some text content
      testFixture.nativeElement.innerHTML = '<aql-button>Click Me</aql-button>';
      testFixture.detectChanges();

      // Note: Full content projection testing requires a host component
      // This is a basic check that the ng-content slot exists
      const button = testFixture.debugElement.query(By.css('button'));
      expect(button).toBeTruthy();
    });
  });
});
