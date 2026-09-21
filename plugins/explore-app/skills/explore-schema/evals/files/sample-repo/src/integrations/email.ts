import nodemailer from 'nodemailer';

const transport = nodemailer.createTransport(process.env.SMTP_URL || 'smtp://localhost:1025');

export async function sendEmail(to: string, subject: string, body: string): Promise<void> {
  await transport.sendMail({ from: 'orders@orderly.example', to, subject, text: body });
}
