"""
Módulo Unificado de Geração de Áudio
Dr. Eduardo Castro - CardioDaily

Wrapper que permite escolher entre OpenAI TTS e ElevenLabs.
Configure via variável de ambiente: CARDIODAILY_AUDIO_PROVIDER

Uso:
    export CARDIODAILY_AUDIO_PROVIDER=openai    # Mais barato (~$0.015/1k chars)
    export CARDIODAILY_AUDIO_PROVIDER=elevenlabs # Voz clonada (~$0.30/1k chars)
"""

import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

# Constante usada pelo article_analyzer para checar disponibilidade
UNIFIED_AUDIO_AVAILABLE = True


def get_audio_generator():
    """
    Factory function que retorna o gerador de áudio apropriado
    baseado na variável de ambiente CARDIODAILY_AUDIO_PROVIDER.
    
    Returns:
        Instância de OpenAIAudioGenerator ou ElevenLabsAudioGenerator
    
    Raises:
        ValueError: Se nenhum provider estiver configurado corretamente
    """
    provider = os.getenv('CARDIODAILY_AUDIO_PROVIDER', 'elevenlabs').lower().strip()
    
    if provider == 'openai':
        try:
            from openai_audio_generator import OpenAIAudioGenerator
            print(f"🎙️  Usando OpenAI TTS (mais econômico)")
            return OpenAIAudioGenerator()
        except ImportError:
            print("⚠️  openai_audio_generator.py não encontrado")
            raise
        except ValueError as e:
            print(f"⚠️  OpenAI não configurado: {e}")
            raise
    
    elif provider == 'elevenlabs':
        try:
            from elevenlabs_audio_generator import ElevenLabsAudioGenerator
            print(f"🎙️  Usando ElevenLabs (voz premium)")
            return ElevenLabsAudioGenerator()
        except ImportError:
            print("⚠️  elevenlabs_audio_generator.py não encontrado")
            raise
        except ValueError as e:
            print(f"⚠️  ElevenLabs não configurado: {e}")
            raise
    
    elif provider == 'auto':
        # Tentar OpenAI primeiro (mais barato), fallback para ElevenLabs
        try:
            from openai_audio_generator import OpenAIAudioGenerator
            if os.getenv('OPENAI_API_KEY'):
                print(f"🎙️  Auto-selecionado: OpenAI TTS")
                return OpenAIAudioGenerator()
        except (ImportError, ValueError):
            pass
        
        try:
            from elevenlabs_audio_generator import ElevenLabsAudioGenerator
            if os.getenv('ELEVENLABS_API_KEY'):
                print(f"🎙️  Auto-selecionado: ElevenLabs")
                return ElevenLabsAudioGenerator()
        except (ImportError, ValueError):
            pass
        
        raise ValueError("Nenhum provider de áudio disponível. Configure OPENAI_API_KEY ou ELEVENLABS_API_KEY")
    
    else:
        raise ValueError(f"Provider de áudio desconhecido: {provider}. Use 'openai', 'elevenlabs' ou 'auto'")


class UnifiedAudioGenerator:
    """
    Classe wrapper que encapsula qualquer provider de áudio.
    Mantém interface consistente independente do backend.
    """
    
    def __init__(self, provider=None):
        """
        Inicializa o gerador unificado.
        
        Args:
            provider: 'openai', 'elevenlabs' ou 'auto' (None usa variável de ambiente)
        """
        if provider:
            os.environ['CARDIODAILY_AUDIO_PROVIDER'] = provider
        
        self._generator = get_audio_generator()
        self.provider = os.getenv('CARDIODAILY_AUDIO_PROVIDER', 'elevenlabs').lower()
    
    def generate_audio(self, text, output_path, **kwargs):
        """
        Gera áudio a partir de texto.
        
        Args:
            text: Texto para converter em áudio
            output_path: Caminho para salvar o arquivo de áudio
            **kwargs: Argumentos específicos do provider
        
        Returns:
            True se sucesso, False caso contrário
        """
        return self._generator.generate_audio(text, output_path, **kwargs)
    
    def list_available_voices(self):
        """Lista vozes disponíveis no provider atual."""
        return self._generator.list_available_voices()
    
    def get_character_count(self):
        """Retorna informações de uso/custo."""
        return self._generator.get_character_count()


# Alias para compatibilidade
AudioGenerator = UnifiedAudioGenerator


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("🧪 TESTE DO MÓDULO UNIFICADO DE ÁUDIO")
    print("=" * 80)
    
    # Mostrar configuração atual
    provider = os.getenv('CARDIODAILY_AUDIO_PROVIDER', 'elevenlabs')
    print(f"\n📋 Provider configurado: {provider}")
    print(f"   (Configure com: export CARDIODAILY_AUDIO_PROVIDER=openai|elevenlabs|auto)")
    
    try:
        # Criar gerador
        generator = UnifiedAudioGenerator()
        
        # Listar vozes
        print("\n1️⃣ Vozes disponíveis:")
        generator.list_available_voices()
        
        # Info de custo
        print("\n2️⃣ Informações de custo:")
        generator.get_character_count()
        
        # Teste de geração
        print("\n3️⃣ Gerando áudio de teste...")
        test_text = "Este é um teste do sistema unificado de geração de áudio do CardioDaily."
        
        success = generator.generate_audio(
            text=test_text,
            output_path="outputs/audio/test_unified.mp3"
        )
        
        if success:
            print("\n✅ Teste concluído com sucesso!")
        else:
            print("\n❌ Teste falhou!")
            
    except Exception as e:
        print(f"\n❌ Erro: {e}")
    
    print("\n" + "=" * 80)
