import os
import dotenv
from telebot import TeleBot
from datetime import datetime, timedelta
from pymongo.mongo_client import MongoClient


dotenv.load_dotenv()

API_KEY = os.getenv('API_KEY')
uri = os.getenv('uri')

bot = TeleBot(API_KEY)

# POSSÍVEIS STATUS
# - entregue
# - cancelado
# - preparo
# - atendendo
# - nome
# - telefone
# - endereco


# FUNÇÃO PARA MENU DE ALTERAÇÃO DE CADASTRO
@bot.message_handler(commands=['alterarCadastro'])
def altCadastro(mensagem):
    entrada = mensagem.json
    idCliente = entrada['from']['id']  
    escolha = str(entrada['text'])[1:]
    cliente, aCompletar = verificaCliente(idCliente)
    
    resposta = ''
    resposta += f"""\
Suas informações atuais são:

 - NOME : {cliente['nome']}
 - ENDEREÇO : {cliente['endereco']}
 - TELEFONE : {cliente['telefone']}

Caso queira alterar algo, selecione uma das opções abaixo:

/nome

/endereco

/telefone

Se deseja cancelar a alteração, selecioen a opção abaixo : 

/cancelar_cadastro
"""
    bot.reply_to(mensagem,resposta)



# FUNÇÃO PARA FINALIZAR O PEDIDO DE MANEIRA POSITIVA OU NEGATIVA
@bot.message_handler(commands=['finalizar','cancelar'])
def fim(mensagem):
    entrada = mensagem.json
    idCliente = entrada['from']['id']  
    escolha = str(entrada['text'])[1:]
    cliente, aCompletar = verificaCliente(idCliente)
    
    #se selecionou essa opção quando não deveria
    if cliente['statusPedido'] != 'atendendo' or len(aCompletar) > 0 or len(cliente['pedido']) == 0:
        resposta = "Algo de errado aconteceu!"
        bot.reply_to(mensagem, resposta) 
        return   
    

    if escolha == 'finalizar':
        resposta = f"""\
Pedido finalizado!

Obrigado pela preferencia!

Seu pedido está sendo preparado e logo chegará em sua casa!
"""
        atualizaDado('statusPedido','preparo',idCliente)
        bot.reply_to(mensagem, resposta) 


    elif escolha == 'cancelar':
        atualizaDado('statusPedido','cancelado',idCliente)
        resetPedido(cliente)
        resposta = f"""\
Pedido cancelado!

Se deseja fazer um pedido, só mandar mensagem que responderemos."""
        bot.reply_to(mensagem, resposta) 

# FUNÇÃO PARA ADICIONAR UM PRODUTO NO CARRINHO
@bot.message_handler(commands=['CupCake_de_morango','CupCake_de_chocolate','CupCake_de_baunilha','CupCake_de_limao'])
def seleciona(mensagem):
    entrada = mensagem.json
    idCliente = entrada['from']['id']
    escolha = str(entrada['text'])[1:]
    
    cliente, aCompletar = verificaCliente(idCliente)
    valortotal = cliente['total']
    
    if cliente['statusPedido'] != 'atendendo' or len(aCompletar) > 0:
        resposta = "Algo de errado aconteceu!"
        bot.reply_to(mensagem, resposta) 
        return

    disponiveis = verificaProdutos()

    ###########
    # RESULTADO
    ###########

    if escolha in disponiveis:

        carrinho = cliente['pedido']
        if (quant := carrinho.get(escolha)) is None:
            carrinho[escolha] = 1
        else:
            carrinho[escolha] = quant + 1

        removeProduto(escolha)
        atualizaDado('pedido',carrinho,idCliente)
        valortotal += disponiveis[escolha]
        atualizaDado('total',valortotal,idCliente)

        resposta = "Escolha registrada com sucesso!\n\n"

    else:
        resposta = "Algo de errado aconteceu com a escolha\n\n"
    bot.reply_to(mensagem, resposta) 
        

    ###################
    # OPCOES DE PRODUTO
    ###################

    resposta = ''
    resposta +="\n##### OPÇÕES DE COMPRA #####\n\n"
    resposta += 'Para adicionar algo em seu carrinho selecione uma das opções abaixo para adicionar nele:\n\n'

    disponiveis = verificaProdutos()
    for disp in disponiveis:
        valor = "{:.2f}".format(disponiveis[disp]/100).replace('.',',')
        resposta += f'/{disp} : R${valor}\n\n'
    bot.reply_to(mensagem, resposta) 

    ##############
    # CARRINHO
    ##############

    resposta = ''
    resposta +="\n##### CARRINHO #####\n\n"
    if len(cliente['pedido']) > 0:
        # resposta += 'Seu carrinho atual é:\n\n'
        for prod in cliente['pedido']:
            resposta += f"- {prod} : X{cliente['pedido'][prod]}\n"
        resposta += '\n'
        total = "{:.2f}".format(valortotal/100).replace('.',',')
        resposta += f'Total do custo : R${total}'
        resposta += '\n'
        bot.reply_to(mensagem, resposta) 

        
        #################
        #FINALIZAR PEDIDO
        #################

        resposta = ''
        resposta +="\n##### FINALIZAR PEDIDO #####\n\n"
        resposta += 'Se deseja finalizar o pedido, aperte o botão "finalizar".\nSe deseja cancelar o pedido, apetre no botão "cancelar"\n\n'
        resposta += '/finalizar\n\n'
        resposta += '/cancelar\n\n'
        bot.reply_to(mensagem, resposta) 
    

# FUNÇÃO PARA ATUALIZAR INFORMAÇÕES DO CLIENTE
@bot.message_handler(commands=['nome','telefone','endereco'])
def atualizar(mensagem):
    entrada = mensagem.json
    idCliente = entrada['from']['id']
    escolha = str(entrada['text'])[1:]

    resposta = f"""\
Por favor digite seu {escolha}"""

    atualizaDado('statusPedido', escolha, idCliente)

    bot.reply_to(mensagem,resposta)


# FUNÇÃO PARA RESPONDER O CLIENTE QUANDO MANDA UMA MENSAGEM QUE NÃO ESTEJA ENTRE AS TRATADAS
@bot.message_handler()
def naoComando(mensagem):
    #################
    #PREPARANDO DADOS
    #################

    dados = (mensagem.json)
    idCliente = dados['from']['id']
    entrada = str(dados['text']).strip()
    cliente, aCompletar = verificaCliente(idCliente)

    # NÃO RESPONDER SE A MENSAGEM FOR IGUAL A "/"
    # USADO PARA TESTE
    if entrada == '/':
        return

    hora=datetime.now().hour
    if hora >= 5 and hora < 12:
        cumprimento = 'Bom dia'
    elif hora >= 12 and hora < 18:
        cumprimento = 'Boa tarde'
    else:
        cumprimento = 'Boa noite'
    
    resposta = ''

    ##############
    # APRESENTACAO
    ##############

    if cliente['statusPedido'] in ('cancelado', 'entregue'):
        resposta = f"""\
{cumprimento}!
Somos um delivery de Cupcakes!
(Esta é uma loja falsa)

"""
        atualizaDado('statusPedido','atendendo',idCliente)
        resetPedido(cliente)
        bot.reply_to(mensagem, resposta) 
    
    elif cliente['statusPedido'] in ['nome','telefone','endereco']:
        resposta += f"""\
{str(cliente['statusPedido']).capitalize()} Atualizado com sucesso!

"""
        if cliente['statusPedido'] in aCompletar : aCompletar.remove(cliente['statusPedido'])
        atualizaDado(cliente['statusPedido'],entrada,idCliente)
        atualizaDado('statusPedido','atendendo',idCliente)

    ############
    # PREPARANDO
    ############

    elif cliente['statusPedido'] == 'preparo':
        resposta = "Estamos lidando com seu pedido e logo ele chegará."
        bot.reply_to(mensagem, resposta) 
        resposta = ''
        for prod in cliente['pedido']:
            resposta += f"- {prod} : X{cliente['pedido'][prod]}\n"
        resposta += '\n'
        bot.reply_to(mensagem, resposta) 
        return

    ##########
    # CADASTRO
    ##########
    resposta = ''
    if len(aCompletar) > 0:
        resposta += '''\
Antes de prosseguir, por favor complete seu cadastro.
Para escolher qual informação deseja informar selecione umas das opções abaixo:

'''
        for campo in aCompletar:
            resposta += f"/{campo}\n\n"
        bot.reply_to(mensagem, resposta) 
        return


    ###################
    # OPCOES DE PRODUTO
    ###################

    resposta = ''
    resposta +="\n##### OPÇÕES DE COMPRA #####\n\n"
    resposta += 'Para adicionar algo em seu carrinho selecione uma das opções abaixo para adicionar nele:\n\n'

    disponiveis = verificaProdutos()
    for disp in disponiveis:
        valor = "{:.2f}".format(disponiveis[disp]/100).replace('.',',')
        resposta += f'/{disp} : R${valor}\n\n'
    bot.reply_to(mensagem, resposta) 


    ##############
    # CARRINHO
    ##############

    resposta = ''
    resposta +="\n##### CARRINHO #####\n\n"
    if len(cliente['pedido']) > 0:
        # resposta += 'Seu carrinho atual é:\n\n'
        for prod in cliente['pedido']:
            resposta += f"- {prod} : X{cliente['pedido'][prod]}\n"
        resposta += '\n'
        total = "{:.2f}".format(cliente['total']/100).replace('.',',')
        resposta += f'Total do custo : R${total}'
        resposta += '\n'
        bot.reply_to(mensagem, resposta) 

        
        #################
        #FINALIZAR PEDIDO
        #################

        resposta = ''
        resposta +="\n##### FINALIZAR PEDIDO #####\n\n"
        resposta += 'Se deseja finalizar o pedido, aperte o botão "finalizar".\nSe deseja cancelar o pedido, apetre no botão "cancelar"\n\n'
        resposta += '/finalizar\n\n'
        resposta += '/cancelar\n\n'
        bot.reply_to(mensagem, resposta) 

        
    else:
        resposta += 'Atualmente se carrinho está vazio!'
        bot.reply_to(mensagem, resposta)

    ##############
    # INFORMAÇÕES DE CADASTRO
    ##############

    resposta = ''
    resposta +="\n##### INFORMAÇÕES DE CADASTRO #####\n\n"
    resposta +="""\
Se deseja alterar informações de cadastro aperte a opção abaixo:

/alterarCadastro\n\n"""
    bot.reply_to(mensagem, resposta) 
    


# FUNÇÃO QUE PROCURA PELO CLIENTE E VERIFICA SE O CADASTRO ESTÁ COMPLETO
def verificaCliente(idCliente):

    encontrado = encontraCliente(idCliente)

    
    if encontrado is None:
        encontrado = {
            'idCliente' : idCliente,
            'nome' : None,
            'telefone' : None,
            'endereco' : None,
            'pedido' : {},
            'statusPedido' : 'cancelado',
            'ultimaInteração' : datetime.now()
        }
        insereCliente(encontrado)
    else:
        if encontrado['ultimaInteração'] <= datetime.now() - timedelta(hours=1):
            atualizaDado('statusPedido','cancelado',idCliente)
            resetPedido(encontrado)
        atualizaDado('ultimaInteração',datetime.now(),idCliente)

    aCompletar = []

    if encontrado['nome'] is None:
        aCompletar.append('nome')
    if encontrado['telefone'] is None:
        aCompletar.append('telefone')
    if encontrado['endereco'] is None:
        aCompletar.append('endereco')
    
    return encontrado, aCompletar


# FUNÇÃO PARA LIMPAR O CARRINHO
def resetPedido(cliente):
    zerado = {}
    pedido = cliente['pedido']
    for produto in pedido:
        # zerado[produto] = 0
        quantidade = pedido[produto]
        adicionaProduto(produto,quantidade)

    atualizaDado('pedido',zerado, cliente['idCliente'])
    atualizaDado('total', 0, cliente['idCliente'])


#FUNÇÃO PARA VERIFICAR SE AINDA TEM O PRODUTO NO ESTOQUE
def verificaProdutos():
    myclient = MongoClient(uri)
    mydb = myclient["mydatabase"]
    mycol = mydb['estoque']
    pesq = mycol.find({})

    disponiveis = {}
    
    for prod in pesq:
        if prod['quantidade'] > 0:
            disponiveis[prod['nome']] = prod['custo']

    return disponiveis


# FUNÇÃO PARA REMOVER UMA UNIDADE DE UM PRODUTO DO ESTOQUE DO ESTOQUE
def removeProduto(nomeProd):
    myclient = MongoClient(uri)
    mydb = myclient["mydatabase"]
    mycol = mydb['estoque']
    produto = mycol.find_one({'nome':nomeProd})
    quantidade = produto['quantidade']

    filtro = {'nome':nomeProd}
    novoValor = {"$set": {'quantidade':quantidade-1}}

    resultado = mycol.update_one(filtro, novoValor)


    return resultado


#FUNÇÃO PARA ADICIONAR UMA QUANTIDADE DE UNIDADES DE UM PRODUTO DO ESTOQUE
def adicionaProduto(nomeProd, quantidade):
    myclient = MongoClient(uri)
    mydb = myclient["mydatabase"]
    mycol = mydb['estoque']
    produto = mycol.find_one({'nome':nomeProd})
    quantAnterior = produto['quantidade']

    filtro = {'nome':nomeProd}
    novoValor = {"$set": {'quantidade': quantAnterior + quantidade}}

    resultado = mycol.update_one(filtro, novoValor)


    return resultado


# FUNÇÃO PARA ENCONTRAR O CLIENTE DENTRO DO BANCO DE DADOS
def encontraCliente(idCliente):
    myclient = MongoClient(uri)
    mydb = myclient["mydatabase"]
    mycol = mydb['clientes']

    cliente = mycol.find_one({'idCliente': idCliente})
    myclient.close()

    return cliente


# FUNÇÃO PARA INSERIR UM NOVO CLIENTE NO BANCO DE DADOS
def insereCliente(cliente):
    myclient = MongoClient(uri)
    mydb = myclient["mydatabase"]
    mycol = mydb['clientes']

    resultado = mycol.insert_one(cliente)
    myclient.close()

    return resultado


# FUNÇÃO PARA ATUALIZAR UM DADO DO CLIENTE NO BANCO DE DADOS
def atualizaDado(chave, valor, id):
    myclient = MongoClient(uri)
    mydb = myclient["mydatabase"]
    mycol = mydb['clientes']

    filtro = {'idCliente':id}
    novoValor = { "$set": {chave:valor}}

    resultado = mycol.update_one(filtro, novoValor)


    myclient.close()

    return resultado


if __name__ == "__main__":
    print('Iniciado')
    bot.polling()
    