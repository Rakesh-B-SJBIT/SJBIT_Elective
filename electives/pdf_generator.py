"""
PDF Generation for SJB Institute Elective System
Generates allocation reports and student certificates
"""

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from django.http import HttpResponse
from django.utils import timezone
from io import BytesIO
import os


class PDFGenerator:
    """Handles PDF generation for various reports"""
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self.setup_custom_styles()
    
    def setup_custom_styles(self):
        """Setup custom paragraph styles"""
        # Header style
        self.styles.add(ParagraphStyle(
            name='CustomHeader',
            parent=self.styles['Heading1'],
            fontSize=18,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#1e3a8a')
        ))
        
        # Subheader style
        self.styles.add(ParagraphStyle(
            name='CustomSubHeader',
            parent=self.styles['Heading2'],
            fontSize=14,
            spaceAfter=20,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#3b82f6')
        ))
        
        # Institution header
        self.styles.add(ParagraphStyle(
            name='InstitutionHeader',
            parent=self.styles['Normal'],
            fontSize=16,
            spaceAfter=10,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#1e3a8a'),
            fontName='Helvetica-Bold'
        ))
        
        # Student info style
        self.styles.add(ParagraphStyle(
            name='StudentInfo',
            parent=self.styles['Normal'],
            fontSize=12,
            spaceAfter=6,
            alignment=TA_LEFT
        ))
    
    def generate_student_allocation_pdf(self, student, allocations):
        """Generate PDF for individual student allocation"""
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72,
                              topMargin=72, bottomMargin=18)
        
        # Container for the 'Flowable' objects
        elements = []
        
        # Institution Header
        elements.append(Paragraph(
            "SJB Institute of Technology Bangalore – 560060",
            self.styles['InstitutionHeader']
        ))
        elements.append(Paragraph(
            "Elective Course Allocation Certificate",
            self.styles['CustomHeader']
        ))
        elements.append(Spacer(1, 20))
        
        # Student Information
        student_data = [
            ['Student Name:', f"{student.user.get_full_name()}"],
            ['Student ID:', student.student_id],
            ['Department:', f"{student.department.name} ({student.department.code})"],
            ['Semester:', f"Semester {student.semester}"],
            ['CGPA:', f"{student.cgpa}"],
            ['Generated On:', timezone.now().strftime('%B %d, %Y at %I:%M %p')]
        ]
        
        student_table = Table(student_data, colWidths=[2*inch, 4*inch])
        student_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#dbeafe')),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#1e3a8a')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        
        elements.append(student_table)
        elements.append(Spacer(1, 30))
        
        # Allocation Results
        if allocations:
            elements.append(Paragraph("Allocated Elective Courses", self.styles['CustomSubHeader']))
            
            # Allocation table
            allocation_data = [['Course Code', 'Course Title', 'Department', 'Credits', 'Status']]
            
            for allocation in allocations:
                status_color = 'green' if allocation.status == 'confirmed' else 'orange'
                allocation_data.append([
                    allocation.course.code,
                    allocation.course.title,
                    allocation.course.department.code,
                    str(allocation.course.credits),
                    allocation.get_status_display()
                ])
            
            allocation_table = Table(allocation_data, colWidths=[1.2*inch, 2.5*inch, 1*inch, 0.8*inch, 1*inch])
            allocation_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a8a')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
            ]))
            
            elements.append(allocation_table)
            elements.append(Spacer(1, 20))
            
            # Summary
            total_credits = sum(a.course.credits for a in allocations if a.status == 'confirmed')
            elements.append(Paragraph(f"<b>Total Credits Allocated:</b> {total_credits}", self.styles['StudentInfo']))
            
        else:
            elements.append(Paragraph("No Elective Courses Allocated", self.styles['CustomSubHeader']))
            elements.append(Paragraph(
                "You have not been allocated any elective courses yet. Please check back after the allocation process is complete.",
                self.styles['Normal']
            ))
        
        elements.append(Spacer(1, 40))
        
        # Footer
        elements.append(Paragraph(
            "This is a computer-generated document and does not require a signature.",
            ParagraphStyle(
                name='Footer',
                parent=self.styles['Normal'],
                fontSize=9,
                alignment=TA_CENTER,
                textColor=colors.grey
            )
        ))
        
        # Build PDF
        doc.build(elements)
        
        # Get the value of the BytesIO buffer and return it
        pdf = buffer.getvalue()
        buffer.close()
        return pdf
    
    def generate_allocation_summary_pdf(self, allocations, title="Allocation Summary Report"):
        """Generate PDF summary of all allocations"""
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72,
                              topMargin=72, bottomMargin=18)
        
        elements = []
        
        # Header
        elements.append(Paragraph(
            "SJB Institute of Technology Bangalore – 560060",
            self.styles['InstitutionHeader']
        ))
        elements.append(Paragraph(title, self.styles['CustomHeader']))
        elements.append(Paragraph(
            f"Generated on {timezone.now().strftime('%B %d, %Y at %I:%M %p')}",
            ParagraphStyle(
                name='DateStyle',
                parent=self.styles['Normal'],
                fontSize=10,
                alignment=TA_CENTER,
                textColor=colors.grey
            )
        ))
        elements.append(Spacer(1, 30))
        
        if allocations:
            # Summary statistics
            total_allocations = len(allocations)
            confirmed_count = len([a for a in allocations if a.status == 'confirmed'])
            waitlisted_count = len([a for a in allocations if a.status == 'waitlisted'])
            
            summary_data = [
                ['Total Allocations:', str(total_allocations)],
                ['Confirmed:', str(confirmed_count)],
                ['Waitlisted:', str(waitlisted_count)],
            ]
            
            summary_table = Table(summary_data, colWidths=[2*inch, 1*inch])
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#dbeafe')),
                ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#1e3a8a')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 11),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 12),
                ('RIGHTPADDING', (0, 0), (-1, -1), 12),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))
            
            elements.append(summary_table)
            elements.append(Spacer(1, 30))
            
            # Detailed allocation table
            elements.append(Paragraph("Detailed Allocation List", self.styles['CustomSubHeader']))
            
            # Table headers
            data = [['Student ID', 'Student Name', 'Department', 'Course Code', 'Course Title', 'Status']]
            
            # Add allocation data
            for allocation in allocations:
                data.append([
                    allocation.student.student_id,
                    allocation.student.user.get_full_name(),
                    allocation.student.department.code,
                    allocation.course.code,
                    allocation.course.title[:30] + ('...' if len(allocation.course.title) > 30 else ''),
                    allocation.get_status_display()
                ])
            
            # Create table
            table = Table(data, colWidths=[1*inch, 1.5*inch, 0.8*inch, 1*inch, 2*inch, 0.8*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a8a')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
            ]))
            
            elements.append(table)
        else:
            elements.append(Paragraph("No allocations found.", self.styles['Normal']))
        
        # Build PDF
        doc.build(elements)
        
        pdf = buffer.getvalue()
        buffer.close()
        return pdf


def generate_student_pdf_response(student, allocations):
    """Generate PDF response for student allocation"""
    generator = PDFGenerator()
    pdf_content = generator.generate_student_allocation_pdf(student, allocations)
    
    response = HttpResponse(pdf_content, content_type='application/pdf')
    filename = f"allocation_{student.student_id}_{timezone.now().strftime('%Y%m%d')}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response


def generate_summary_pdf_response(allocations, title="Allocation Summary Report"):
    """Generate PDF response for allocation summary"""
    generator = PDFGenerator()
    pdf_content = generator.generate_allocation_summary_pdf(allocations, title)
    
    response = HttpResponse(pdf_content, content_type='application/pdf')
    filename = f"allocation_summary_{timezone.now().strftime('%Y%m%d_%H%M')}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response